import json
import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import mlflow
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.datasets import load_breast_cancer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ARTIFACT_DIR = Path(os.getenv("ARTIFACT_DIR", "artifacts"))
TRAINING_DATA_PATH = os.getenv("TRAINING_DATA_PATH")
TARGET_COLUMN = os.getenv("TARGET_COLUMN")

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns")
MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "drift-triage")


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}

    if isinstance(value, list):
        return [json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [json_safe(item) for item in value]

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, np.ndarray):
        return value.tolist()

    if pd.isna(value):
        return None

    return value


def load_training_data() -> tuple[pd.DataFrame, pd.Series, str]:
    if TRAINING_DATA_PATH and TARGET_COLUMN:
        data_path = Path(TRAINING_DATA_PATH)

        if not data_path.exists():
            raise FileNotFoundError(f"Training data not found: {data_path}")

        df = pd.read_csv(data_path)

        if TARGET_COLUMN not in df.columns:
            raise ValueError(f"Target column '{TARGET_COLUMN}' not found in CSV.")

        X = df.drop(columns=[TARGET_COLUMN])
        y = df[TARGET_COLUMN]

        return X, y, TARGET_COLUMN

    dataset = load_breast_cancer(as_frame=True)
    X = dataset.data
    y = dataset.target

    return X, y, "target"


def build_pipeline() -> Pipeline:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                numeric_pipeline,
                make_column_selector(dtype_include=np.number),
            ),
            (
                "categorical",
                categorical_pipeline,
                make_column_selector(dtype_exclude=np.number),
            ),
        ],
        remainder="drop",
    )

    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        random_state=42,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )


def choose_threshold(y_true: pd.Series, probabilities: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)

    if len(thresholds) == 0:
        return 0.5

    f1_scores = []

    for index, threshold in enumerate(thresholds):
        p = precision[index]
        r = recall[index]

        if p + r == 0:
            f1_scores.append(0.0)
        else:
            f1_scores.append(2 * p * r / (p + r))

    best_index = int(np.argmax(f1_scores))

    return float(thresholds[best_index])


def evaluate(y_true: pd.Series, probabilities: np.ndarray, threshold: float) -> dict[str, float]:
    predictions = (probabilities >= threshold).astype(int)

    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "auc": float(roc_auc_score(y_true, probabilities)),
    }


def build_schema(X: pd.DataFrame, target_column: str) -> dict[str, Any]:
    features = {}

    for column in X.columns:
        dtype = str(X[column].dtype)

        if pd.api.types.is_numeric_dtype(X[column]):
            kind = "numeric"
        else:
            kind = "categorical"

        features[column] = {
            "dtype": dtype,
            "kind": kind,
        }

    return {
        "target_column": target_column,
        "feature_names": list(X.columns),
        "features": features,
    }


def numeric_reference(series: pd.Series) -> dict[str, Any]:
    values = pd.to_numeric(series, errors="coerce").dropna()

    if values.empty:
        return {
            "kind": "numeric",
            "bins": [0.0, 1.0],
            "reference_distribution": [1],
            "mean": None,
            "std": None,
        }

    quantiles = np.linspace(0, 1, 11)
    bins = np.quantile(values, quantiles)
    bins = np.unique(bins)

    if len(bins) < 3:
        minimum = float(values.min())
        maximum = float(values.max())

        if minimum == maximum:
            bins = np.array([minimum - 0.5, minimum + 0.5])
        else:
            bins = np.linspace(minimum, maximum, 11)

    counts, bin_edges = np.histogram(values, bins=bins)

    return {
        "kind": "numeric",
        "bins": [float(edge) for edge in bin_edges],
        "reference_distribution": [int(count) for count in counts],
        "mean": float(values.mean()),
        "std": float(values.std()),
        "min": float(values.min()),
        "max": float(values.max()),
    }


def categorical_reference(series: pd.Series) -> dict[str, Any]:
    values = series.astype(str).fillna("__missing__")
    counts = values.value_counts(dropna=False)

    categories = [str(category) for category in counts.index.tolist()]
    distribution = [int(count) for count in counts.values.tolist()]

    return {
        "kind": "categorical",
        "categories": categories,
        "reference_distribution": distribution,
    }


def build_reference_stats(
    X_reference: pd.DataFrame,
    reference_probabilities: np.ndarray,
    reference_predictions: np.ndarray,
) -> dict[str, Any]:
    features = {}

    for column in X_reference.columns:
        if pd.api.types.is_numeric_dtype(X_reference[column]):
            features[column] = numeric_reference(X_reference[column])
        else:
            features[column] = categorical_reference(X_reference[column])

    probability_bins = np.linspace(0, 1, 11)
    probability_counts, probability_edges = np.histogram(
        reference_probabilities,
        bins=probability_bins,
    )

    class_counts = pd.Series(reference_predictions).value_counts().sort_index()

    return {
        "created_at": datetime.utcnow().isoformat(),
        "n_rows": int(len(X_reference)),
        "features": features,
        "output": {
            "class_distribution": {
                str(key): int(value) for key, value in class_counts.to_dict().items()
            },
            "probability_bins": [float(edge) for edge in probability_edges],
            "probability_reference_distribution": [
                int(count) for count in probability_counts.tolist()
            ],
        },
    }


def save_json(path: Path, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(json_safe(data), file, indent=2)


def save_model_card(
    path: Path,
    *,
    metrics: dict[str, Any],
    threshold: float,
    feature_names: list[str],
    target_column: str,
) -> None:
    content = f"""# Drift Triage Model Card

## Purpose

This model predicts the probability of the positive class for the drift triage co-pilot project.

## Target

Target column: `{target_column}`

## Features

Number of input features: `{len(feature_names)}`

## Operating Threshold

Selected threshold: `{threshold:.4f}`

## Metrics

```json
{json.dumps(json_safe(metrics), indent=2)}"""