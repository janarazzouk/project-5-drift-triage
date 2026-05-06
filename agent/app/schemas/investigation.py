from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.contracts.drift_webhook import DriftSeverity


InvestigationStatus = Literal[
    "open",
    "running",
    "waiting_for_job",
    "waiting_for_approval",
    "resolved",
    "failed",
]


class InvestigationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str

    model_name: str
    model_version: str | None

    severity: DriftSeverity
    status: InvestigationStatus | str

    current_step: str

    recommended_action: str | None
    production_action_required: bool

    approval_id: str | None

    summary: str | None

    graph_thread_id: str

    state_json: dict[str, Any]
    result_json: dict[str, Any] | None

    opened_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class InvestigationListResponse(BaseModel):
    investigations: list[InvestigationRead]
    total: int


class InvestigationSummaryResponse(BaseModel):
    investigation: InvestigationRead
    messages: list[dict[str, Any]]
    jobs: list[dict[str, Any]]
    approvals: list[dict[str, Any]]