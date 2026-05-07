from sqlalchemy.orm import sessionmaker

from app.repositories.worker_job_repository import WorkerJobRepository
from app.schemas.job import WorkerJobEnvelope


class JobLogService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
    ):
        self.session_factory = session_factory
        self.repository = WorkerJobRepository()

    def mark_processing(
        self,
        job: WorkerJobEnvelope,
        *,
        attempts: int,
    ) -> None:
        db = self.session_factory()

        try:
            self.repository.mark_processing(
                db,
                job=job,
                attempts=attempts,
            )
        finally:
            db.close()

    def mark_completed(
        self,
        job: WorkerJobEnvelope,
        *,
        result: dict | None,
        attempts: int,
    ) -> None:
        db = self.session_factory()

        try:
            self.repository.mark_completed(
                db,
                job=job,
                result=result,
                attempts=attempts,
            )
        finally:
            db.close()

    def mark_retrying(
        self,
        job: WorkerJobEnvelope,
        *,
        error_message: str,
        attempts: int,
    ) -> None:
        db = self.session_factory()

        try:
            self.repository.mark_retrying(
                db,
                job=job,
                error_message=error_message,
                attempts=attempts,
            )
        finally:
            db.close()

    def mark_dlq(
        self,
        job: WorkerJobEnvelope,
        *,
        error_message: str,
        attempts: int,
        result: dict | None = None,
    ) -> None:
        db = self.session_factory()

        try:
            self.repository.mark_dlq(
                db,
                job=job,
                error_message=error_message,
                attempts=attempts,
                result=result,
            )
        finally:
            db.close()

    def mark_skipped_duplicate(
        self,
        job: WorkerJobEnvelope,
    ) -> None:
        db = self.session_factory()

        try:
            self.repository.mark_skipped_duplicate(
                db,
                job=job,
            )
        finally:
            db.close()