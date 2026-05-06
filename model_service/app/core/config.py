from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
MODEL_SERVICE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_prefix="MODEL_SERVICE_",
        extra="ignore",
    )

    service_name: str = "drift-triage-model-service"
    service_version: str = "0.1.0"

    artifact_dir: Path = MODEL_SERVICE_DIR / "artifacts"

    model_path: Path | None = None
    schema_path: Path | None = None
    runtime_config_path: Path | None = None
    reference_stats_path: Path | None = None
    metrics_path: Path | None = None
    environment_path: Path | None = None
    replay_fixture_path: Path | None = None
    model_card_path: Path | None = None

    database_url: str = "sqlite:///./model_service.db"

    mlflow_tracking_uri: str = "file:./mlruns"
    mlflow_experiment_name: str = "drift-triage"
    mlflow_model_name: str = "drift-triage-model"

    drift_recent_window_size: int = 200
    drift_min_samples: int = 30
    drift_warning_threshold: float = 0.10
    drift_critical_threshold: float = 0.25

    agent_drift_webhook_url: str | None = None

    allow_extra_features: bool = False

    @property
    def resolved_model_path(self) -> Path:
        return self.model_path or self.artifact_dir / "model_pipeline.joblib"

    @property
    def resolved_schema_path(self) -> Path:
        return self.schema_path or self.artifact_dir / "schema.json"

    @property
    def resolved_runtime_config_path(self) -> Path:
        return self.runtime_config_path or self.artifact_dir / "runtime_config.json"

    @property
    def resolved_reference_stats_path(self) -> Path:
        return self.reference_stats_path or self.artifact_dir / "reference_stats.json"

    @property
    def resolved_metrics_path(self) -> Path:
        return self.metrics_path or self.artifact_dir / "metrics.json"

    @property
    def resolved_environment_path(self) -> Path:
        return self.environment_path or self.artifact_dir / "environment.json"

    @property
    def resolved_replay_fixture_path(self) -> Path:
        return self.replay_fixture_path or self.artifact_dir / "replay_fixture.json"

    @property
    def resolved_model_card_path(self) -> Path:
        return self.model_card_path or self.artifact_dir / "model_card.md"


@lru_cache
def get_settings() -> Settings:
    return Settings()