from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_queue_service
from app.core.errors import NotFoundError
from app.schemas.queue import (
    JobRecordRead,
    JobResultCallbackRequest,
    JobResultCallbackResponse,
    QueueStatusResponse,
)
from app.services.queue_service import QueueService


router = APIRouter(tags=["queue"])


@router.get("/queue/status", response_model=QueueStatusResponse)
def get_queue_status(
    db: Session = Depends(get_db),
    queue_service: QueueService = Depends(get_queue_service),
    limit: int = Query(default=50, ge=1, le=200),
) -> QueueStatusResponse:
    return queue_service.get_queue_status(
        db,
        limit=limit,
    )


@router.get("/queue/jobs", response_model=list[JobRecordRead])
def list_jobs(
    db: Session = Depends(get_db),
    queue_service: QueueService = Depends(get_queue_service),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
) -> list[JobRecordRead]:
    return queue_service.job_repository.list_recent(
        db,
        limit=limit,
        offset=offset,
        status=status,
    )


@router.get("/queue/jobs/{job_id}", response_model=JobRecordRead)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    queue_service: QueueService = Depends(get_queue_service),
) -> JobRecordRead:
    job = queue_service.job_repository.get_by_job_id(
        db,
        job_id,
    )

    if job is None:
        raise NotFoundError(f"Job not found: {job_id}")

    return job


@router.post("/queue/jobs/result", response_model=JobResultCallbackResponse)
def record_job_result(
    payload: JobResultCallbackRequest,
    db: Session = Depends(get_db),
    queue_service: QueueService = Depends(get_queue_service),
) -> JobResultCallbackResponse:
    return queue_service.record_job_result(
        db,
        payload,
    )