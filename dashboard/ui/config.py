import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DASHBOARD_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DASHBOARD_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(DASHBOARD_DIR / ".env", override=False)


@dataclass(frozen=True)
class DashboardConfig:
    agent_api_url: str
    model_service_api_url: str
    request_timeout_seconds: float


def load_dashboard_config() -> DashboardConfig:
    return DashboardConfig(
        agent_api_url=os.getenv("AGENT_API_URL", "http://127.0.0.1:8010").rstrip("/"),
        model_service_api_url=os.getenv(
            "MODEL_SERVICE_API_URL",
            "http://127.0.0.1:8000",
        ).rstrip("/"),
        request_timeout_seconds=float(os.getenv("DASHBOARD_REQUEST_TIMEOUT_SECONDS", "8")),
    )