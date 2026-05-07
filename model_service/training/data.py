from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split


@dataclass(frozen=True)
class DataSplits:
    X_train: pd.DataFrame
    X_val: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_val: pd.Series
    y_test: pd.Series


def load_bank_marketing_data(
    data_path: Path,
    *,
    target_column: str,
) -> tuple[pd.DataFrame, pd.Series]:
    if not data_path.exists():
        raise FileNotFoundError(
            f"Training data not found at {data_path}. Check TRAINING_DATA_PATH in .env."
        )

    df = pd.read_csv(data_path, sep=";")

    if target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' not found in {data_path}.")

    if "duration" not in df.columns:
        raise ValueError(
            "Expected column 'duration' was not found. "
            "It must be dropped to avoid label leakage."
        )

    target_values = df[target_column]

    if target_values.dtype == "object":
        normalized = target_values.astype(str).str.strip().str.lower()
        unexpected_values = sorted(set(normalized.unique()) - {"yes", "no"})

        if unexpected_values:
            raise ValueError(
                f"Target column '{target_column}' must only contain yes/no values. "
                f"Found: {unexpected_values}"
            )

        y = normalized.map({"no": 0, "yes": 1}).astype(int)
    else:
        y = target_values.astype(int)

    X = df.drop(columns=[target_column, "duration"]).copy()

    if "pdays" not in X.columns:
        raise ValueError("Expected column 'pdays' was not found in the training data.")

    X["pdays_was_999"] = (X["pdays"] == 999).astype(int)
    X["pdays"] = X["pdays"].replace(999, -1)

    return X, y


def get_feature_groups(X: pd.DataFrame) -> tuple[list[str], list[str]]:
    numeric_features = [
        column for column in X.columns if pd.api.types.is_numeric_dtype(X[column])
    ]
    categorical_features = [column for column in X.columns if column not in numeric_features]

    return numeric_features, categorical_features


def make_train_val_test_split(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    random_state: int,
) -> DataSplits:
    X_train, X_temp, y_train, y_temp = train_test_split(
        X,
        y,
        train_size=0.60,
        random_state=random_state,
        stratify=y,
    )

    X_val, X_test, y_val, y_test = train_test_split(
        X_temp,
        y_temp,
        test_size=0.50,
        random_state=random_state,
        stratify=y_temp,
    )

    return DataSplits(
        X_train=X_train,
        X_val=X_val,
        X_test=X_test,
        y_train=y_train,
        y_val=y_val,
        y_test=y_test,
    )