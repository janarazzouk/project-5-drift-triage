import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import redis
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import QueueError
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.job_repository import JobRepository
from app.schemas.queue import (
    EnqueueJobResponse,
    JobResultCallbackRequest,
    JobResultCallbackResponse,
    QueueStatusResponse,
)


class QueueService:
    def __init__(
        self,
        *,
        settings: Settings,
        redis_client: redis.Redis,
    ):
        self.settings = settings
        self.redis_client = redis_client
        self.job_repository = JobRepository()
        self.message_repository = AgentMessageRepository()

    def enqueue_job(
        self,
        db: Session,
        *,
        investigation_id: str,
        job_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> EnqueueJobResponse:
        job_id = f"job_{uuid4().hex[:12]}"
        idempotency_key = (
            idempotency_key
            or f"{job_type}:{investigation_id}:{payload.get('model_version', 'unknown')}"
        )

        job_record, duplicate = self.job_repository.create_if_not_exists(
            db,
            job_id=job_id,
            idempotency_key=idempotency_key,
            investigation_id=investigation_id,
            job_type=job_type,
            payload=payload,
            max_attempts=self.settings.job_max_attempts,
        )

        if duplicate:
            return EnqueueJobResponse(
                queued=False,
                duplicate=True,
                job_id=job_record.job_id,
                idempotency_key=job_record.idempotency_key,
                message="Duplicate job was not re-queued.",
            )

        envelope = {
            "job_id": job_record.job_id,
            "idempotency_key": job_record.idempotency_key,
            "investigation_id": investigation_id,
            "job_type": job_type,
            "payload": payload,
            "attempts": 0,
            "max_attempts": self.settings.job_max_attempts,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            self.redis_client.lpush(
                self.settings.queue_name,
                json.dumps(envelope),
            )
        except redis.RedisError as exc:
            self.job_repository.mark_failed(
                db,
                job_id=job_record.job_id,
                error_message=str(exc),
            )

            raise QueueError(f"Failed to enqueue job in Redis: {exc}") from exc

        self.message_repository.create_system_message(
            db,
            investigation_id=investigation_id,
            node_name="queue",
            content=f"Queued {job_type} job {job_record.job_id}.",
            metadata={
                "job_id": job_record.job_id,
                "idempotency_key": job_record.idempotency_key,
                "job_type": job_type,
            },
        )

        return EnqueueJobResponse(
            queued=True,
            duplicate=False,
            job_id=job_record.job_id,
            idempotency_key=job_record.idempotency_key,
            message="Job queued successfully.",
        )

    def get_queue_status(
        self,
        db: Session,
        *,
        limit: int = 50,
    ) -> QueueStatusResponse:
        pending_count = int(self.redis_client.llen(self.settings.queue_name))
        processing_count = int(
            self.redis_client.llen(self.settings.queue_processing_name)
        )
        dlq_count = int(self.redis_client.llen(self.settings.queue_dlq_name))

        tracked_jobs = self.job_repository.list_recent(db, limit=limit)

        return QueueStatusResponse(
            queue_name=self.settings.queue_name,
            pending_count=pending_count,
            processing_count=processing_count,
            dlq_count=dlq_count,
            tracked_jobs=tracked_jobs,
        )

    def record_job_result(
        self,
        db: Session,
        payload: JobResultCallbackRequest,
    ) -> JobResultCallbackResponse:
        if payload.status == "completed":
            record = self.job_repository.mark_completed(
                db,
                job_id=payload.job_id,
                result=payload.result,
                attempts=payload.attempts,
            )
            message_type = "tool_result"
            content = f"Job {payload.job_id} completed."
        elif payload.status == "dlq":
            record = self.job_repository.mark_dlq(
                db,
                job_id=payload.job_id,
                reason=payload.error_message or "Job moved to DLQ.",
                attempts=payload.attempts,
                result=payload.result,
            )
            message_type = "dlq"
            content = f"Job {payload.job_id} moved to DLQ."
        else:
            record = self.job_repository.mark_failed(
                db,
                job_id=payload.job_id,
                error_message=payload.error_message or "Job failed.",
                attempts=payload.attempts,
            )
            message_type = "tool_error"
            content = f"Job {payload.job_id} failed."

        if record is None:
            raise QueueError(f"Unknown job_id: {payload.job_id}")

        self.message_repository.create_tool_message(
            db,
            investigation_id=payload.investigation_id,
            node_name=payload.job_type,
            content=content,
            metadata={
                "job_id": payload.job_id,
                "job_type": payload.job_type,
                "status": payload.status,
                "result": payload.result,
                "error_message": payload.error_message,
            },
        )

        return JobResultCallbackResponse(
            accepted=True,
            job_id=payload.job_id,
            investigation_id=payload.investigation_id,
            message="Job result recorded.",
        )