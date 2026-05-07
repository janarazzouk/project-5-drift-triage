import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


MODEL_SERVICE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = MODEL_SERVICE_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(MODEL_SERVICE_DIR / ".env", override=False)


@dataclass(frozen=True)
class TrainingConfig:
    random_state: int
    target_column: str
    training_data_path: Path
    artifact_dir: Path
    min_recall: float
    mlflow_tracking_uri: str
    mlflow_experiment_name: str
    mlflow_model_name: str
    archive_existing_artifacts: bool


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y"}


def _resolve_existing_path(value: str | Path) -> Path:
    path = Path(value).expanduser()

    if path.is_absolute():
        return path

    project_path = PROJECT_ROOT / path
    if project_path.exists():
        return project_path

    model_service_path = MODEL_SERVICE_DIR / path
    if model_service_path.exists():
        return model_service_path

    return project_path


def _resolve_output_path(value: str | Path) -> Path:
    path = Path(value).expanduser()

    if path.is_absolute():
        return path

    if path.parts and path.parts[0] == "model_service":
        return PROJECT_ROOT / path

    return MODEL_SERVICE_DIR / path


def load_training_config() -> TrainingConfig:
    training_data_path = os.getenv(
        "TRAINING_DATA_PATH",
        os.getenv("MODEL_SERVICE_TRAINING_DATA_PATH", "data/raw/bank-additional-full.csv"),
    )

    artifact_dir = os.getenv(
        "TRAINING_ARTIFACT_DIR",
        os.getenv("ARTIFACT_DIR", os.getenv("MODEL_SERVICE_ARTIFACT_DIR", "artifacts")),
    )

    return TrainingConfig(
        random_state=int(os.getenv("TRAINING_RANDOM_STATE", "42")),
        target_column=os.getenv("TARGET_COLUMN", "y"),
        training_data_path=_resolve_existing_path(training_data_path),
        artifact_dir=_resolve_output_path(artifact_dir),
        min_recall=float(os.getenv("TRAINING_MIN_RECALL", "0.74")),
        mlflow_tracking_uri=os.getenv(
            "MLFLOW_TRACKING_URI",
            os.getenv("MODEL_SERVICE_MLFLOW_TRACKING_URI", "file:./mlruns"),
        ),
        mlflow_experiment_name=os.getenv(
            "MLFLOW_EXPERIMENT_NAME",
            os.getenv("MODEL_SERVICE_MLFLOW_EXPERIMENT_NAME", "drift-triage"),
        ),
        mlflow_model_name=os.getenv(
            "MLFLOW_MODEL_NAME",
            os.getenv(
                "MODEL_SERVICE_MLFLOW_MODEL_NAME",
                "drift-triage-bank-marketing-classifier",
            ),
        ),
        archive_existing_artifacts=_env_bool("ARCHIVE_EXISTING_ARTIFACTS", True),
    )