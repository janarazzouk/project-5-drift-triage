from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


JobType = Literal[
    "replay_test",
    "retrain",
    "rollback",
]


JobStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "retrying",
    "dlq",
    "skipped_duplicate",
]


class JobRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int

    job_id: str
    idempotency_key: str

    investigation_id: str

    job_type: JobType | str
    status: JobStatus | str

    payload_json: dict[str, Any]
    result_json: dict[str, Any] | None
    error_message: str | None

    attempts: int
    max_attempts: int

    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    next_retry_at: datetime | None

    sent_to_dlq: bool
    dlq_reason: str | None

    created_at: datetime
    updated_at: datetime


class QueueStatusResponse(BaseModel):
    queue_name: str
    pending_count: int
    processing_count: int
    dlq_count: int
    tracked_jobs: list[JobRecordRead]


class EnqueueJobResponse(BaseModel):
    queued: bool
    duplicate: bool = False
    job_id: str
    idempotency_key: str
    message: str


class JobResultCallbackRequest(BaseModel):
    job_id: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)
    investigation_id: str = Field(..., min_length=1)
    job_type: JobType | str

    status: Literal["completed", "failed", "dlq"]

    result: dict[str, Any] | None = None
    error_message: str | None = None

    attempts: int = Field(..., ge=0)
    finished_at: datetime


class JobResultCallbackResponse(BaseModel):
    accepted: bool
    job_id: str
    investigation_id: str
    message: str