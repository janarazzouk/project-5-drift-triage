from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.contracts.drift_webhook import DriftSeverity


AgentNodeName = Literal[
    "supervisor",
    "triage",
    "action",
    "comms",
    "approval",
    "completion",
]


class AgentMessageRead(BaseModel):
    id: int
    investigation_id: str
    role: str
    node_name: str | None
    message_type: str
    content: str
    metadata_json: dict[str, Any] | None
    created_at: datetime


class TriageDecision(BaseModel):
    severity: DriftSeverity
    risk_level: Literal["low", "medium", "high", "unknown"]
    primary_issue: str
    explanation: str
    drifted_features: list[str] = Field(default_factory=list)


class ActionDecision(BaseModel):
    recommended_action: Literal[
        "monitor",
        "replay_test",
        "retrain",
        "rollback_production",
        "promote_to_production",
        "resolve",
    ]
    production_action_required: bool
    queue_job_required: bool
    reason: str


class AgentRunResult(BaseModel):
    investigation_id: str
    event_id: str
    status: str
    current_step: str
    recommended_action: str | None = None
    production_action_required: bool = False
    approval_id: str | None = None
    queued_job_ids: list[str] = Field(default_factory=list)
    summary: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)


class AgentErrorResponse(BaseModel):
    error: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)