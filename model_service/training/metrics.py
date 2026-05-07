import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def choose_highest_threshold_for_recall(
    y_true: pd.Series,
    probabilities: np.ndarray,
    *,
    min_recall: float,
) -> float:
    if int(np.sum(y_true)) == 0:
        return 0.5

    candidates = np.unique(np.concatenate(([0.0, 0.5, 1.0], probabilities)))
    valid_thresholds: list[float] = []

    for threshold in candidates:
        predictions = (probabilities >= threshold).astype(int)
        recall = recall_score(y_true, predictions, zero_division=0)

        if recall >= min_recall:
            valid_thresholds.append(float(threshold))

    if valid_thresholds:
        return max(valid_thresholds)

    recalls = []

    for threshold in candidates:
        predictions = (probabilities >= threshold).astype(int)
        recalls.append(recall_score(y_true, predictions, zero_division=0))

    best_index = int(np.argmax(recalls))
    return float(candidates[best_index])


def evaluate(
    y_true: pd.Series,
    probabilities: np.ndarray,
    *,
    threshold: float,
) -> dict[str, float]:
    predictions = (probabilities >= threshold).astype(int)

    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "auc": float(roc_auc_score(y_true, probabilities)),
        "f1": float(f1_score(y_true, predictions, zero_division=0)),
        "precision": float(precision_score(y_true, predictions, zero_division=0)),
        "recall": float(recall_score(y_true, predictions, zero_division=0)),
    }


def prefix_metrics(prefix: str, metrics: dict[str, float]) -> dict[str, float]:
    return {f"{prefix}_{key}": value for key, value in metrics.items()}