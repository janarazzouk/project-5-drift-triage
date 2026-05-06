from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.job_record import JobRecord


class JobRepository:
    def get_by_job_id(
        self,
        db: Session,
        job_id: str,
    ) -> JobRecord | None:
        return (
            db.query(JobRecord)
            .filter(JobRecord.job_id == job_id)
            .first()
        )

    def get_by_idempotency_key(
        self,
        db: Session,
        idempotency_key: str,
    ) -> JobRecord | None:
        return (
            db.query(JobRecord)
            .filter(JobRecord.idempotency_key == idempotency_key)
            .first()
        )

    def create(
        self,
        db: Session,
        *,
        job_id: str,
        idempotency_key: str,
        investigation_id: str,
        job_type: str,
        payload: dict[str, Any],
        max_attempts: int = 3,
    ) -> JobRecord:
        record = JobRecord(
            job_id=job_id,
            idempotency_key=idempotency_key,
            investigation_id=investigation_id,
            job_type=job_type,
            status="queued",
            payload_json=payload,
            max_attempts=max_attempts,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record

    def create_if_not_exists(
        self,
        db: Session,
        *,
        job_id: str,
        idempotency_key: str,
        investigation_id: str,
        job_type: str,
        payload: dict[str, Any],
        max_attempts: int = 3,
    ) -> tuple[JobRecord, bool]:
        existing = self.get_by_idempotency_key(db, idempotency_key)

        if existing is not None:
            return existing, True

        record = self.create(
            db,
            job_id=job_id,
            idempotency_key=idempotency_key,
            investigation_id=investigation_id,
            job_type=job_type,
            payload=payload,
            max_attempts=max_attempts,
        )

        return record, False

    def list_by_investigation(
        self,
        db: Session,
        investigation_id: str,
    ) -> list[JobRecord]:
        return (
            db.query(JobRecord)
            .filter(JobRecord.investigation_id == investigation_id)
            .order_by(JobRecord.created_at.desc())
            .all()
        )

    def list_recent(
        self,
        db: Session,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[JobRecord]:
        query = db.query(JobRecord)

        if status is not None:
            query = query.filter(JobRecord.status == status)

        return (
            query.order_by(JobRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count(
        self,
        db: Session,
        *,
        status: str | None = None,
    ) -> int:
        query = db.query(JobRecord)

        if status is not None:
            query = query.filter(JobRecord.status == status)

        return query.count()

    def mark_running(
        self,
        db: Session,
        *,
        job_id: str,
        attempts: int | None = None,
    ) -> JobRecord | None:
        record = self.get_by_job_id(db, job_id)

        if record is None:
            return None

        record.status = "running"
        record.started_at = datetime.utcnow()

        if attempts is not None:
            record.attempts = attempts

        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record

    def mark_completed(
        self,
        db: Session,
        *,
        job_id: str,
        result: dict[str, Any] | None = None,
        attempts: int | None = None,
    ) -> JobRecord | None:
        record = self.get_by_job_id(db, job_id)

        if record is None:
            return None

        record.status = "completed"
        record.result_json = result
        record.finished_at = datetime.utcnow()
        record.error_message = None

        if attempts is not None:
            record.attempts = attempts

        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record

    def mark_failed(
        self,
        db: Session,
        *,
        job_id: str,
        error_message: str,
        attempts: int | None = None,
    ) -> JobRecord | None:
        record = self.get_by_job_id(db, job_id)

        if record is None:
            return None

        record.status = "failed"
        record.error_message = error_message
        record.finished_at = datetime.utcnow()

        if attempts is not None:
            record.attempts = attempts

        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record

    def mark_retrying(
        self,
        db: Session,
        *,
        job_id: str,
        error_message: str,
        attempts: int,
        next_retry_at: datetime,
    ) -> JobRecord | None:
        record = self.get_by_job_id(db, job_id)

        if record is None:
            return None

        record.status = "retrying"
        record.error_message = error_message
        record.attempts = attempts
        record.next_retry_at = next_retry_at
        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record

    def mark_dlq(
        self,
        db: Session,
        *,
        job_id: str,
        reason: str,
        attempts: int | None = None,
        result: dict[str, Any] | None = None,
    ) -> JobRecord | None:
        record = self.get_by_job_id(db, job_id)

        if record is None:
            return None

        record.status = "dlq"
        record.sent_to_dlq = True
        record.dlq_reason = reason
        record.result_json = result
        record.finished_at = datetime.utcnow()

        if attempts is not None:
            record.attempts = attempts

        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record

    def mark_skipped_duplicate(
        self,
        db: Session,
        *,
        job_id: str,
        result: dict[str, Any] | None = None,
    ) -> JobRecord | None:
        record = self.get_by_job_id(db, job_id)

        if record is None:
            return None

        record.status = "skipped_duplicate"
        record.result_json = result
        record.finished_at = datetime.utcnow()
        record.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(record)

        return record