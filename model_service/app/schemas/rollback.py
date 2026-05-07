from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RollbackRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    contract_version: Literal["v1"] = "v1"
    request_type: Literal["rollback.production.requested"] = (
        "rollback.production.requested"
    )

    request_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    source_service: str = "worker"

    investigation_id: str = Field(..., min_length=1)
    approval_id: str = Field(..., min_length=1)

    requested_action: Literal["rollback_production"] = "rollback_production"
    target_environment: Literal["production"] = "production"

    model_name: str = Field(..., min_length=1)
    model_version: str | None = None

    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RollbackResponse(BaseModel):
    rolled_back: bool
    duplicate: bool = False

    request_id: str

    investigation_id: str
    approval_id: str

    model_name: str
    model_version: str | None

    target_environment: str

    previous_stage: str | None = None
    new_stage: str | None = None

    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    completed_at: datetime