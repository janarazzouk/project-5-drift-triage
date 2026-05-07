from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


JobStatus = Literal[
    "completed",
    "failed",
    "dlq",
]


class WorkerJobEnvelope(BaseModel):
    job_id: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)
    investigation_id: str = Field(..., min_length=1)

    job_type: str = Field(..., min_length=1)

    payload: dict[str, Any] = Field(default_factory=dict)

    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)

    queued_at: str | None = None


class JobResultPayload(BaseModel):
    job_id: str
    idempotency_key: str
    investigation_id: str
    job_type: str

    status: JobStatus

    result: dict[str, Any] | None = None
    error_message: str | None = None

    attempts: int
    finished_at: datetime