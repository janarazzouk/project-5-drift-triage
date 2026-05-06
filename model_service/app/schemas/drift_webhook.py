from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DriftSeverity = Literal[
    "insufficient_data",
    "normal",
    "warning",
    "critical",
]


class DriftWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["v1"] = "v1"
    event_type: Literal["drift.severity_changed"] = "drift.severity_changed"

    event_id: str = Field(..., min_length=1)
    created_at: datetime

    source_service: Literal["model_service"] = "model_service"

    model_name: str = Field(..., min_length=1)
    model_version: str | None = None

    previous_severity: DriftSeverity
    new_severity: DriftSeverity

    overall_score: float = Field(..., ge=0)
    sample_size: int = Field(..., ge=0)
    min_required_samples: int = Field(..., ge=0)

    drift_report: dict[str, Any]

    metadata: dict[str, Any] = Field(default_factory=dict)