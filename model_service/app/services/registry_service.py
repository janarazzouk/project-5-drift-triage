import json
from pathlib import Path
from typing import Any

import mlflow

from app.core.config import Settings
from app.services.prediction_service import Predictor

#This file reads model information from artifacts.
def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""

    with open(path, "r", encoding="utf-8") as file:
        return file.read()


class RegistryClient:
    def __init__(self, settings: Settings, predictor: Predictor):
        self.settings = settings
        self.predictor = predictor

        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    def get_model_info(self) -> dict[str, Any]:
        metrics = read_json_if_exists(self.settings.resolved_metrics_path)
        environment = read_json_if_exists(self.settings.resolved_environment_path)
        model_card = read_text_if_exists(self.settings.resolved_model_card_path)

        return {
            "model_name": self.settings.mlflow_model_name,
            "model_version": self.predictor.model_version,
            "threshold": self.predictor.threshold,
            "metrics": metrics,
            "environment": environment,
            "model_card_preview": model_card[:1000],
            "artifact_paths": {
                "model": str(self.settings.resolved_model_path),
                "schema": str(self.settings.resolved_schema_path),
                "runtime_config": str(self.settings.resolved_runtime_config_path),
                "reference_stats": str(self.settings.resolved_reference_stats_path),
                "metrics": str(self.settings.resolved_metrics_path),
                "environment": str(self.settings.resolved_environment_path),
                "replay_fixture": str(self.settings.resolved_replay_fixture_path),
                "model_card": str(self.settings.resolved_model_card_path),
            },
        }