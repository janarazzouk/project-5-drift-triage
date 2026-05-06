from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.drift_webhook import DriftSeverity


class HumanApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: Literal[True]
    approved_by: str = Field(..., min_length=1)
    approved_at: datetime
    approval_source: Literal["dashboard"] = "dashboard"


class PromotionDriftContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1)
    severity: DriftSeverity
    previous_model_version: str | None = None


class PromotionRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["v1"] = "v1"
    request_type: Literal[
        "promotion.production.requested"
    ] = "promotion.production.requested"

    request_id: str = Field(..., min_length=1)
    created_at: datetime

    source_service: Literal["agent"] = "agent"

    investigation_id: str = Field(..., min_length=1)
    approval_id: str = Field(..., min_length=1)

    requested_action: Literal["promote_to_production"] = "promote_to_production"
    target_environment: Literal["production"] = "production"

    model_name: str = Field(..., min_length=1)
    model_version: str = Field(..., min_length=1)

    human_approval: HumanApproval

    reason: str = Field(..., min_length=1)

    drift_context: PromotionDriftContext | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)