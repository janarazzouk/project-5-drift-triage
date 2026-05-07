import json
import platform
from pathlib import Path
from typing import Any

import joblib
import mlflow
import numpy as np
import pandas as pd
import sklearn

from training.io_utils import json_safe, utc_now


def build_schema(
    X: pd.DataFrame,
    *,
    target_column: str,
    numeric_features: list[str],
    categorical_features: list[str],
) -> dict[str, Any]:
    return {
        "input_columns": list(X.columns),
        "target_column": target_column,
        "dropped_columns": ["duration"],
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "feature_types": {column: str(X[column].dtype) for column in X.columns},
        "special_handling": {
            "pdays": {
                "sentinel_original_value": 999,
                "replacement_value": -1,
                "flag_column": "pdays_was_999",
            },
            "unknown_values": "kept as real categories",
        },
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
            "min": None,
            "max": None,
        }

    bins = np.unique(np.quantile(values, np.linspace(0, 1, 11)))

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
        "reference_distribution": [int(count) for count in counts.tolist()],
        "mean": float(values.mean()),
        "std": float(values.std(ddof=0)),
        "min": float(values.min()),
        "max": float(values.max()),
        "median": float(values.median()),
        "q25": float(values.quantile(0.25)),
        "q75": float(values.quantile(0.75)),
        "missing_count": int(series.isna().sum()),
    }


def categorical_reference(series: pd.Series) -> dict[str, Any]:
    values = series.fillna("__missing__").astype(str)
    counts = values.value_counts(dropna=False)

    return {
        "kind": "categorical",
        "categories": [str(category) for category in counts.index.tolist()],
        "reference_distribution": [int(count) for count in counts.values.tolist()],
        "missing_count": int(series.isna().sum()),
        "n_unique": int(values.nunique(dropna=False)),
    }


def build_reference_stats(
    *,
    X_reference: pd.DataFrame,
    y_reference: pd.Series,
    reference_probabilities: np.ndarray,
    reference_predictions: np.ndarray,
    numeric_features: list[str],
    categorical_features: list[str],
) -> dict[str, Any]:
    features: dict[str, Any] = {}

    for column in X_reference.columns:
        if column in numeric_features:
            features[column] = numeric_reference(X_reference[column])
        elif column in categorical_features:
            features[column] = categorical_reference(X_reference[column])

    probability_counts, probability_edges = np.histogram(
        reference_probabilities,
        bins=np.linspace(0, 1, 11),
    )

    class_counts = pd.Series(reference_predictions).value_counts().sort_index()
    target_distribution = y_reference.value_counts(normalize=True).sort_index()

    return {
        "created_at": utc_now(),
        "n_rows": int(len(X_reference)),
        "target_distribution": {
            str(key): float(value) for key, value in target_distribution.to_dict().items()
        },
        "features": features,
        "output": {
            "class_distribution": {
                str(key): int(value) for key, value in class_counts.to_dict().items()
            },
            "probability_bins": [float(edge) for edge in probability_edges.tolist()],
            "probability_reference_distribution": [
                int(count) for count in probability_counts.tolist()
            ],
        },
    }


def build_replay_fixture(
    *,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    probabilities: np.ndarray,
    threshold: float,
    random_state: int,
    sample_size: int = 20,
) -> dict[str, Any]:
    fixture_df = X_test.copy()
    fixture_df["actual_class"] = y_test.to_numpy()
    fixture_df["probability"] = probabilities
    fixture_df["predicted_class"] = (probabilities >= threshold).astype(int)

    positives = fixture_df[fixture_df["actual_class"] == 1]
    negatives = fixture_df[fixture_df["actual_class"] == 0]

    positive_sample_size = min(len(positives), max(1, sample_size // 2))
    negative_sample_size = min(len(negatives), sample_size - positive_sample_size)

    sampled = pd.concat(
        [
            positives.sample(n=positive_sample_size, random_state=random_state)
            if positive_sample_size > 0
            else positives,
            negatives.sample(n=negative_sample_size, random_state=random_state)
            if negative_sample_size > 0
            else negatives,
        ]
    )

    if len(sampled) < sample_size:
        remaining = fixture_df.drop(index=sampled.index, errors="ignore")
        extra = remaining.sample(
            n=min(sample_size - len(sampled), len(remaining)),
            random_state=random_state,
        )
        sampled = pd.concat([sampled, extra])

    sampled = sampled.sample(frac=1, random_state=random_state).reset_index(drop=True)

    rows: list[dict[str, Any]] = []
    expected_probabilities: list[float] = []
    expected_predictions: list[int] = []
    actual_classes: list[int] = []

    for _, row in sampled.iterrows():
        rows.append({column: json_safe(row[column]) for column in X_test.columns})
        expected_probabilities.append(float(row["probability"]))
        expected_predictions.append(int(row["predicted_class"]))
        actual_classes.append(int(row["actual_class"]))

    return {
        "description": "Small replay fixture from test set for prediction consistency checks.",
        "selected_threshold": float(threshold),
        "rows": rows,
        "expected_probabilities": expected_probabilities,
        "expected_predictions": expected_predictions,
        "actual_classes": actual_classes,
    }


def build_environment() -> dict[str, Any]:
    return {
        "created_at": utc_now(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": {
            "joblib": joblib.__version__,
            "mlflow": mlflow.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }


def build_runtime_config_base(
    *,
    selected_threshold: float,
    artifact_dir: Path,
    data_path: Path,
    target_column: str,
    random_state: int,
    train_rows: int,
    val_rows: int,
    test_rows: int,
) -> dict[str, Any]:
    return {
        "selected_threshold": selected_threshold,
        "local_model_binary": str(artifact_dir / "model_pipeline.joblib"),
        "schema_path": str(artifact_dir / "schema.json"),
        "reference_stats_path": str(artifact_dir / "reference_stats.json"),
        "replay_fixture_path": str(artifact_dir / "replay_fixture.json"),
        "training_data_path": str(data_path),
        "target_column": target_column,
        "created_at": utc_now(),
        "split": {
            "train_rows": int(train_rows),
            "val_rows": int(val_rows),
            "test_rows": int(test_rows),
            "random_state": random_state,
            "stratified": True,
        },
    }


def save_model_card(
    path: Path,
    *,
    metrics: dict[str, Any],
    selected_threshold: float,
    data_path: Path,
    artifact_dir: Path,
    target_column: str,
    min_recall: float,
    mlflow_model_name: str,
    model_version: str,
    mlflow_run_id: str,
    numeric_features: list[str],
    categorical_features: list[str],
) -> None:
    content = f"""# Drift Triage Bank Marketing Model Card

## Purpose

This model predicts whether a bank marketing client is likely to subscribe to a term deposit.
It is used by the Drift Triage Co-pilot project for prediction, drift checks, replay tests, and retraining experiments.

## Training Data

- Dataset path: `{data_path}`
- Target column: `{target_column}`
- Positive class: `yes` mapped to `1`
- Negative class: `no` mapped to `0`

## Preprocessing

- Dropped `duration` to avoid label leakage.
- Converted `pdays == 999` into `pdays_was_999 = 1` and replaced `pdays` with `-1`.
- Kept `unknown` values as normal categorical values.
- Used a 60/20/20 stratified train/validation/test split.
- Numeric features use median imputation and standard scaling.
- Categorical features use most-frequent imputation and one-hot encoding.

## Features

- Numeric features: `{len(numeric_features)}`
- Categorical features: `{len(categorical_features)}`

## Operating Threshold

Selected threshold: `{selected_threshold:.6f}`

The threshold is selected from the validation set as the highest threshold where recall is at least `{min_recall:.2f}`.

## MLflow

- Registered model name: `{mlflow_model_name}`
- Model version: `{model_version}`
- MLflow run id: `{mlflow_run_id}`

## Local Artifacts

Artifacts were saved in:

`{artifact_dir}`

## Metrics

```json
{json.dumps(json_safe(metrics), indent=2)}
"""
    path.write_text(content, encoding="utf-8")