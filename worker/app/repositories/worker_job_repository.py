from typing import Any

from sqlalchemy.orm import Session

from app.models.worker_job import WorkerJob
from app.schemas.job import WorkerJobEnvelope


class WorkerJobRepository:
    def get_by_job_id(
        self,
        db: Session,
        job_id: str,
    ) -> WorkerJob | None:
        return db.query(WorkerJob).filter(WorkerJob.job_id == job_id).first()

    def mark_processing(
        self,
        db: Session,
        *,
        job: WorkerJobEnvelope,
        attempts: int,
    ) -> WorkerJob:
        record = self._get_or_create(
            db,
            job=job,
            status="processing",
        )

        record.status = "processing"
        record.attempts = attempts
        record.max_attempts = job.max_attempts
        record.error_message = None
        record.completed = False
        record.sent_to_dlq = False

        db.commit()
        db.refresh(record)

        return record

    def mark_completed(
        self,
        db: Session,
        *,
        job: WorkerJobEnvelope,
        result: dict[str, Any] | None,
        attempts: int,
    ) -> WorkerJob:
        record = self._get_or_create(
            db,
            job=job,
            status="completed",
        )

        record.status = "completed"
        record.result_json = result
        record.error_message = None
        record.attempts = attempts
        record.completed = True
        record.sent_to_dlq = False

        db.commit()
        db.refresh(record)

        return record

    def mark_retrying(
        self,
        db: Session,
        *,
        job: WorkerJobEnvelope,
        error_message: str,
        attempts: int,
    ) -> WorkerJob:
        record = self._get_or_create(
            db,
            job=job,
            status="retrying",
        )

        record.status = "retrying"
        record.error_message = error_message
        record.attempts = attempts
        record.completed = False
        record.sent_to_dlq = False

        db.commit()
        db.refresh(record)

        return record

    def mark_dlq(
        self,
        db: Session,
        *,
        job: WorkerJobEnvelope,
        error_message: str,
        attempts: int,
        result: dict[str, Any] | None = None,
    ) -> WorkerJob:
        record = self._get_or_create(
            db,
            job=job,
            status="dlq",
        )

        record.status = "dlq"
        record.result_json = result
        record.error_message = error_message
        record.attempts = attempts
        record.completed = False
        record.sent_to_dlq = True

        db.commit()
        db.refresh(record)

        return record

    def mark_skipped_duplicate(
        self,
        db: Session,
        *,
        job: WorkerJobEnvelope,
    ) -> WorkerJob:
        record = self._get_or_create(
            db,
            job=job,
            status="skipped_duplicate",
        )

        record.status = "skipped_duplicate"
        record.completed = True

        db.commit()
        db.refresh(record)

        return record

    def _get_or_create(
        self,
        db: Session,
        *,
        job: WorkerJobEnvelope,
        status: str,
    ) -> WorkerJob:
        record = self.get_by_job_id(
            db,
            job.job_id,
        )

        if record is not None:
            return record

        record = WorkerJob(
            job_id=job.job_id,
            idempotency_key=job.idempotency_key,
            investigation_id=job.investigation_id,
            job_type=job.job_type,
            status=status,
            payload_json=job.model_dump(mode="json"),
            result_json=None,
            error_message=None,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            completed=False,
            sent_to_dlq=False,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record