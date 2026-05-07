import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def build_pipeline(
    numeric_features: list[str],
    categorical_features: list[str],
    *,
    random_state: int,
) -> Pipeline:
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
            ("numeric", numeric_pipeline, numeric_features),
            ("categorical", categorical_pipeline, categorical_features),
        ],
        remainder="drop",
    )

    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        random_state=random_state,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", model),
        ]
    )


def predict_positive_probability(model: Pipeline, X: pd.DataFrame) -> np.ndarray:
    if not hasattr(model, "predict_proba"):
        raise ValueError("The trained model must support predict_proba().")

    probabilities = model.predict_proba(X)

    if probabilities.ndim != 2 or probabilities.shape[1] < 2:
        raise ValueError("Expected binary classification probabilities with 2 columns.")

    return probabilities[:, 1]