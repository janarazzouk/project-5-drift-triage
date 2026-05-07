from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
WORKER_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_prefix="WORKER_",
        extra="ignore",
    )

    service_name: str = "drift-triage-worker"
    service_version: str = "0.1.0"
    environment: str = "local"

    database_url: str = (
        "postgresql+psycopg2://postgres:password@localhost:5432/drift_triage"
    )

    redis_url: str = "redis://localhost:6379/0"

    queue_name: str = "drift_triage_jobs"
    queue_processing_name: str = "drift_triage_jobs_processing"
    queue_dlq_name: str = "drift_triage_jobs_dlq"

    agent_url: str = "http://127.0.0.1:8010"
    agent_timeout_seconds: float = 10.0
    agent_job_result_path: str = "/queue/jobs/result"

    model_service_url: str = "http://127.0.0.1:8000"
    model_service_timeout_seconds: float = 30.0

    worker_poll_timeout_seconds: int = 5
    worker_idle_sleep_seconds: float = 1.0

    job_max_attempts: int = 3
    job_base_retry_delay_seconds: int = 2
    job_idempotency_ttl_seconds: int = 60 * 60 * 24

    retrain_command: str = "uv run python train.py"
    retrain_working_dir: Path = ROOT_DIR / "model_service"
    retrain_timeout_seconds: int = 60 * 20

    rollback_endpoint_path: str = "/rollback/production"

    @property
    def agent_job_result_url(self) -> str:
        return f"{self.agent_url.rstrip('/')}{self.agent_job_result_path}"

    @property
    def model_service_replay_compare_url(self) -> str:
        return f"{self.model_service_url.rstrip('/')}/replay-fixture/compare"

    @property
    def model_service_health_url(self) -> str:
        return f"{self.model_service_url.rstrip('/')}/health"

    @property
    def model_service_rollback_url(self) -> str:
        return f"{self.model_service_url.rstrip('/')}{self.rollback_endpoint_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()