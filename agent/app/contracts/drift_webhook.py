from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DriftSeverity = Literal[
    "insufficient_data",
    "normal",
    "warning",
    "critical",
]


class DriftFeatureResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature: str = Field(..., min_length=1)
    kind: Literal["numeric", "categorical", "unknown"]
    score: float = Field(..., ge=0)
    severity: DriftSeverity
    details: dict[str, Any] = Field(default_factory=dict)


class OutputDriftResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: str = Field(..., min_length=1)
    score: float = Field(..., ge=0)
    severity: DriftSeverity


class DriftReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_size: int = Field(..., ge=0)
    min_required_samples: int = Field(..., ge=0)
    severity: DriftSeverity
    overall_score: float = Field(..., ge=0)
    features: list[DriftFeatureResult] = Field(default_factory=list)
    output_drift: OutputDriftResult | dict[str, Any] | None = None


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

    drift_report: DriftReport | dict[str, Any]

    metadata: dict[str, Any] = Field(default_factory=dict)


class DriftWebhookResponse(BaseModel):
    accepted: bool
    duplicate: bool = False
    event_id: str
    investigation_id: str | None = None
    message: str