import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import chisquare
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import PredictionRecord


EPSILON = 1e-6


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize_distribution(values: list[float]) -> np.ndarray:
    array = np.array(values, dtype=float)
    total = array.sum()

    if total <= 0:
        return np.ones_like(array) / len(array)

    return array / total


def psi(expected: list[float], actual: list[float]) -> float:
    expected_array = normalize_distribution(expected)
    actual_array = normalize_distribution(actual)

    expected_array = np.clip(expected_array, EPSILON, None)
    actual_array = np.clip(actual_array, EPSILON, None)

    return float(np.sum((actual_array - expected_array) * np.log(actual_array / expected_array)))


def severity_from_score(
    score: float,
    *,
    warning_threshold: float,
    critical_threshold: float,
) -> str:
    if score >= critical_threshold:
        return "critical"

    if score >= warning_threshold:
        return "warning"

    return "normal"


class DriftService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.reference_stats = load_json(settings.resolved_reference_stats_path)

    def analyze(self, db: Session) -> dict[str, Any]:
        records = (
            db.query(PredictionRecord)
            .order_by(PredictionRecord.created_at.desc())
            .limit(self.settings.drift_recent_window_size)
            .all()
        )

        records = list(reversed(records))

        if len(records) < self.settings.drift_min_samples:
            return {
                "sample_size": len(records),
                "min_required_samples": self.settings.drift_min_samples,
                "severity": "insufficient_data",
                "overall_score": 0.0,
                "features": [],
                "output_drift": None,
            }

        feature_rows = [record.features_json for record in records]
        recent_df = pd.DataFrame(feature_rows)

        feature_results = []
        overall_score = 0.0

        reference_features = self.reference_stats.get("features", {})

        for feature_name, reference in reference_features.items():
            if feature_name not in recent_df.columns:
                continue

            kind = reference.get("kind", "unknown")

            if kind == "numeric":
                result = self._numeric_drift(feature_name, recent_df[feature_name], reference)
            else:
                result = self._categorical_drift(feature_name, recent_df[feature_name], reference)

            feature_results.append(result)
            overall_score = max(overall_score, result["score"])

        output_result = self._output_drift(records)

        if output_result:
            overall_score = max(overall_score, output_result.get("score", 0.0))

        overall_severity = severity_from_score(
            overall_score,
            warning_threshold=self.settings.drift_warning_threshold,
            critical_threshold=self.settings.drift_critical_threshold,
        )

        return {
            "sample_size": len(records),
            "min_required_samples": self.settings.drift_min_samples,
            "severity": overall_severity,
            "overall_score": overall_score,
            "features": feature_results,
            "output_drift": output_result,
        }

    def _numeric_drift(
        self,
        feature_name: str,
        series: pd.Series,
        reference: dict[str, Any],
    ) -> dict[str, Any]:
        bins = reference.get("bins")
        expected_distribution = reference.get("reference_distribution")

        if not bins or not expected_distribution:
            return {
                "feature": feature_name,
                "kind": "numeric",
                "score": 0.0,
                "severity": "unknown",
                "details": {"reason": "Missing reference bins or distribution."},
            }

        numeric_values = pd.to_numeric(series, errors="coerce").dropna()

        actual_counts, _ = np.histogram(numeric_values, bins=bins)
        actual_distribution = actual_counts.tolist()

        score = psi(expected_distribution, actual_distribution)

        severity = severity_from_score(
            score,
            warning_threshold=self.settings.drift_warning_threshold,
            critical_threshold=self.settings.drift_critical_threshold,
        )

        return {
            "feature": feature_name,
            "kind": "numeric",
            "score": score,
            "severity": severity,
            "details": {
                "bins": bins,
                "actual_distribution": actual_distribution,
                "expected_distribution": expected_distribution,
            },
        }

    def _categorical_drift(
        self,
        feature_name: str,
        series: pd.Series,
        reference: dict[str, Any],
    ) -> dict[str, Any]:
        categories = reference.get("categories", [])
        expected_distribution = reference.get("reference_distribution", [])

        if not categories or not expected_distribution:
            return {
                "feature": feature_name,
                "kind": "categorical",
                "score": 0.0,
                "severity": "unknown",
                "details": {"reason": "Missing reference categories or distribution."},
            }

        values = series.astype(str)
        actual_counts = [int((values == str(category)).sum()) for category in categories]

        unknown_count = int(~values.isin([str(category) for category in categories]).sum())

        score = psi(expected_distribution, actual_counts)

        expected_counts = normalize_distribution(expected_distribution) * max(sum(actual_counts), 1)

        try:
            chi_square_stat, p_value = chisquare(
                f_obs=np.array(actual_counts) + EPSILON,
                f_exp=expected_counts + EPSILON,
            )
        except ValueError:
            chi_square_stat, p_value = None, None

        severity = severity_from_score(
            score,
            warning_threshold=self.settings.drift_warning_threshold,
            critical_threshold=self.settings.drift_critical_threshold,
        )

        return {
            "feature": feature_name,
            "kind": "categorical",
            "score": score,
            "severity": severity,
            "details": {
                "categories": categories,
                "actual_distribution": actual_counts,
                "expected_distribution": expected_distribution,
                "unknown_count": unknown_count,
                "chi_square_stat": chi_square_stat,
                "chi_square_p_value": p_value,
            },
        }

    def _output_drift(self, records: list[PredictionRecord]) -> dict[str, Any] | None:
        reference_output = self.reference_stats.get("output")

        if not reference_output:
            return None

        probability_bins = reference_output.get("probability_bins")
        probability_reference_distribution = reference_output.get(
            "probability_reference_distribution"
        )

        if not probability_bins or not probability_reference_distribution:
            return None

        probabilities = np.array([record.probability for record in records], dtype=float)
        actual_counts, _ = np.histogram(probabilities, bins=probability_bins)

        score = psi(probability_reference_distribution, actual_counts.tolist())

        severity = severity_from_score(
            score,
            warning_threshold=self.settings.drift_warning_threshold,
            critical_threshold=self.settings.drift_critical_threshold,
        )

        return {
            "kind": "output_probability",
            "score": score,
            "severity": severity,
            "probability_bins": probability_bins,
            "actual_distribution": actual_counts.tolist(),
            "expected_distribution": probability_reference_distribution,
        }