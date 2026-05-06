import json
import uuid
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.config import Settings


class Predictor:
    def __init__(self, settings: Settings):
        self.settings = settings

        self.model = joblib.load(settings.resolved_model_path)
        self.schema = self._load_json(settings.resolved_schema_path)
        self.runtime_config = self._load_json(settings.resolved_runtime_config_path)

        self.threshold = float(
            self.runtime_config.get("selected_threshold")
            or self.runtime_config.get("threshold")
            or 0.5
        )

        self.model_version = self.runtime_config.get("model_version")

        self.input_columns = self._extract_input_columns()
        self.numeric_features = set(self.schema.get("numeric_features", []))
        self.categorical_features = set(self.schema.get("categorical_features", []))
        self.feature_types = self.schema.get("feature_types", {})
        self.dropped_columns = set(self.schema.get("dropped_columns", []))
        self.special_handling = self.schema.get("special_handling", {})

    def _load_json(self, path: Path) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _extract_input_columns(self) -> list[str]:
        if "input_columns" in self.schema:
            return list(self.schema["input_columns"])

        if "feature_names" in self.schema:
            return list(self.schema["feature_names"])

        if "features" in self.schema:
            return list(self.schema["features"].keys())

        if "columns" in self.schema:
            return list(self.schema["columns"])

        raise ValueError(
            "schema.json must contain one of: input_columns, feature_names, features, or columns."
        )

    def validate_and_prepare_features(self, features: dict[str, Any]) -> dict[str, Any]:
        prepared = dict(features)

        prepared = self._drop_training_dropped_columns(prepared)
        prepared = self._apply_special_handling(prepared)

        missing = [column for column in self.input_columns if column not in prepared]

        if missing:
            raise ValueError(f"Missing required feature(s): {missing}")

        extra = [column for column in prepared if column not in self.input_columns]

        if extra and not self.settings.allow_extra_features:
            raise ValueError(f"Unexpected extra feature(s): {extra}")

        validated: dict[str, Any] = {}

        for column in self.input_columns:
            value = prepared[column]

            if value is None:
                raise ValueError(f"Feature '{column}' cannot be null.")

            if column in self.numeric_features:
                validated[column] = self._convert_numeric(column, value)
            elif column in self.categorical_features:
                validated[column] = self._convert_categorical(column, value)
            else:
                validated[column] = self._convert_by_dtype(column, value)

        return validated

    def _drop_training_dropped_columns(self, features: dict[str, Any]) -> dict[str, Any]:
        for column in self.dropped_columns:
            features.pop(column, None)

        return features

    def _apply_special_handling(self, features: dict[str, Any]) -> dict[str, Any]:
        pdays_config = self.special_handling.get("pdays")

        if not pdays_config:
            return features

        pdays_column = "pdays"
        flag_column = pdays_config.get("flag_column", "pdays_was_999")
        sentinel_value = pdays_config.get("sentinel_original_value", 999)
        replacement_value = pdays_config.get("replacement_value", -1)

        if pdays_column not in features:
            return features

        try:
            pdays_value = int(features[pdays_column])
        except (TypeError, ValueError) as exc:
            raise ValueError("Feature 'pdays' must be numeric.") from exc

        if pdays_value == sentinel_value:
            features[pdays_column] = replacement_value
            features[flag_column] = 1
        else:
            features[pdays_column] = pdays_value
            features.setdefault(flag_column, 0)

        return features

    def _convert_numeric(self, column: str, value: Any) -> int | float:
        expected_type = self.feature_types.get(column, "")

        try:
            if expected_type.startswith("int"):
                return int(value)

            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Feature '{column}' must be numeric. Got: {value}"
            ) from exc

    def _convert_categorical(self, column: str, value: Any) -> str:
        if isinstance(value, str):
            cleaned = value.strip()

            if cleaned == "":
                raise ValueError(f"Feature '{column}' cannot be an empty string.")

            return cleaned

        return str(value)

    def _convert_by_dtype(self, column: str, value: Any) -> Any:
        expected_type = self.feature_types.get(column, "")

        if expected_type.startswith("int"):
            return int(value)

        if expected_type.startswith("float"):
            return float(value)

        if expected_type == "object":
            return str(value)

        return value

    def predict(
        self,
        features: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        request_id = request_id or str(uuid.uuid4())

        validated_features = self.validate_and_prepare_features(features)

        input_df = pd.DataFrame(
            [validated_features],
            columns=self.input_columns,
        )

        probability = self._predict_probability(input_df)
        predicted_class = int(probability >= self.threshold)

        return {
            "request_id": request_id,
            "features": validated_features,
            "probability": probability,
            "predicted_class": predicted_class,
            "threshold": self.threshold,
            "model_version": self.model_version,
        }

    def _predict_probability(self, input_df: pd.DataFrame) -> float:
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(input_df)

            if probabilities.ndim == 2 and probabilities.shape[1] > 1:
                return float(probabilities[0, 1])

            return float(probabilities[0])

        if hasattr(self.model, "decision_function"):
            score = float(self.model.decision_function(input_df)[0])
            return float(1 / (1 + np.exp(-score)))

        prediction = self.model.predict(input_df)[0]
        return float(prediction)