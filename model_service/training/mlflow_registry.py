
from pathlib import Path
from typing import Any

import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.pipeline import Pipeline

from training.config import TrainingConfig
from training.io_utils import ARTIFACT_FILES, save_json


def log_and_register_model(
    *,
    config: TrainingConfig,
    model: Pipeline,
    artifact_dir: Path,
    metrics: dict[str, float],
    selected_threshold: float,
    runtime_config_base: dict[str, Any],
    X_example: pd.DataFrame,
) -> tuple[str, str, str]:
    mlflow.set_tracking_uri(config.mlflow_tracking_uri)
    mlflow.set_experiment(config.mlflow_experiment_name)

    with mlflow.start_run() as run:
        mlflow_run_id = run.info.run_id

        mlflow.log_param("dataset_path", str(config.training_data_path))
        mlflow.log_param("target_column", config.target_column)
        mlflow.log_param("dropped_columns", "duration")
        mlflow.log_param("pdays_999_handling", "flag:pdays_was_999,replacement:-1")
        mlflow.log_param("split", "60/20/20 stratified")
        mlflow.log_param("min_recall", config.min_recall)
        mlflow.log_param("selected_threshold", selected_threshold)

        for metric_name, metric_value in metrics.items():
            mlflow.log_metric(metric_name, float(metric_value))

        for artifact_name in ARTIFACT_FILES:
            artifact_path = artifact_dir / artifact_name
            if artifact_path.exists():
                mlflow.log_artifact(str(artifact_path))

        model_info = mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=config.mlflow_model_name,
            input_example=X_example.head(5),
        )

        model_version = _find_registered_model_version(
            model_name=config.mlflow_model_name,
            run_id=mlflow_run_id,
            model_info=model_info,
        )

        runtime_config = {
            **runtime_config_base,
            "registered_model_name": config.mlflow_model_name,
            "mlflow_run_id": mlflow_run_id,
            "model_version": model_version,
            "model_artifact_path": "model",
            "mlflow_model_uri": model_info.model_uri,
        }

        save_json(artifact_dir / "runtime_config.json", runtime_config)
        mlflow.log_artifact(str(artifact_dir / "runtime_config.json"))

        mlflow.set_tag("model_version", model_version)
        mlflow.set_tag("project", "drift-triage-co-pilot")
        mlflow.set_tag("training_script", "model_service/train.py")

        return mlflow_run_id, model_version, model_info.model_uri


def log_extra_artifacts_to_run(
    *,
    mlflow_tracking_uri: str,
    mlflow_run_id: str,
    artifact_paths: list[Path],
) -> None:
    mlflow.set_tracking_uri(mlflow_tracking_uri)

    with mlflow.start_run(run_id=mlflow_run_id):
        for artifact_path in artifact_paths:
            if artifact_path.exists():
                mlflow.log_artifact(str(artifact_path))


def _find_registered_model_version(
    *,
    model_name: str,
    run_id: str,
    model_info: Any,
) -> str:
    if getattr(model_info, "registered_model_version", None) is not None:
        return str(model_info.registered_model_version)

    client = mlflow.MlflowClient()
    versions = client.search_model_versions(f"name = '{model_name}'")
    run_versions = [version for version in versions if version.run_id == run_id]

    if not run_versions:
        raise RuntimeError(
            "MLflow logged the model but did not return a registered model version."
        )

    return str(max(int(version.version) for version in run_versions))