from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ApprovalStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "expired",
]


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str

    investigation_id: str

    requested_action: str
    target_environment: str

    model_name: str
    model_version: str | None

    status: ApprovalStatus | str

    reason: str

    approved: bool | None
    approved_by: str | None
    approved_at: datetime | None

    rejected_by: str | None
    rejected_at: datetime | None
    rejection_reason: str | None

    request_payload_json: dict[str, Any] | None
    decision_payload_json: dict[str, Any] | None

    created_at: datetime
    updated_at: datetime


class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalRead]
    total: int


class ApprovalDecisionRequest(BaseModel):
    approved_by: str = Field(..., min_length=1)
    note: str | None = None


class ApprovalRejectionRequest(BaseModel):
    rejected_by: str = Field(..., min_length=1)
    rejection_reason: str = Field(..., min_length=1)


class ApprovalDecisionResponse(BaseModel):
    approval: ApprovalRead
    investigation_id: str
    message: str