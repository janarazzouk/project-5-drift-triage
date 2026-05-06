from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
AGENT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_prefix="AGENT_",
        extra="ignore",
    )

    service_name: str = "drift-triage-agent"
    service_version: str = "0.1.0"
    environment: str = "local"

    api_host: str = "0.0.0.0"
    api_port: int = 8010

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/drift_triage_agent"
    )

    langgraph_checkpoint_db_uri: str = (
        "postgresql://postgres:postgres@localhost:5432/drift_triage_agent"
    )

    redis_url: str = "redis://localhost:6379/0"

    model_service_url: str = "http://127.0.0.1:8000"
    model_service_timeout_seconds: float = 10.0

    dashboard_url: str | None = None

    contract_version: str = "v1"

    drift_webhook_path: str = "/webhooks/drift"

    queue_name: str = "drift_triage_jobs"
    queue_processing_name: str = "drift_triage_jobs_processing"
    queue_dlq_name: str = "drift_triage_jobs_dlq"

    job_result_callback_path: str = "/queue/jobs/result"

    job_max_attempts: int = 3
    job_base_retry_delay_seconds: int = 2
    job_idempotency_ttl_seconds: int = 60 * 60 * 24

    replay_job_enabled: bool = True
    retrain_job_enabled: bool = True
    rollback_job_enabled: bool = True

    approval_stale_after_minutes: int = 60

    llm_provider: str = "mock"
    llm_model: str = "mock-deterministic"
    llm_temperature: float = 0.0

    prompt_dir: Path = AGENT_DIR / "app" / "agents" / "prompts"

    allowed_drift_severities: set[str] = Field(
        default_factory=lambda: {
            "insufficient_data",
            "normal",
            "warning",
            "critical",
        }
    )

    production_actions: set[str] = Field(
        default_factory=lambda: {
            "promote_to_production",
            "rollback_production",
        }
    )

    @property
    def model_service_promotion_url(self) -> str:
        return f"{self.model_service_url.rstrip('/')}/promotion/production"

    @property
    def model_service_replay_compare_url(self) -> str:
        return f"{self.model_service_url.rstrip('/')}/replay-fixture/compare"

    @property
    def model_service_health_url(self) -> str:
        return f"{self.model_service_url.rstrip('/')}/health"


@lru_cache
def get_settings() -> Settings:
    return Settings()