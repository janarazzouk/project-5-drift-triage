from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_investigation_service
from app.core.errors import NotFoundError
from app.schemas.investigation import (
    InvestigationListResponse,
    InvestigationRead,
    InvestigationSummaryResponse,
)
from app.services.investigation_service import InvestigationService


router = APIRouter(tags=["investigations"])


@router.get("/investigations", response_model=InvestigationListResponse)
def list_investigations(
    db: Session = Depends(get_db),
    investigation_service: InvestigationService = Depends(get_investigation_service),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
) -> InvestigationListResponse:
    investigations, total = investigation_service.list_investigations(
        db,
        limit=limit,
        offset=offset,
        status=status,
    )

    return InvestigationListResponse(
        investigations=investigations,
        total=total,
    )


@router.get("/investigations/open", response_model=InvestigationListResponse)
def list_open_investigations(
    db: Session = Depends(get_db),
    investigation_service: InvestigationService = Depends(get_investigation_service),
    limit: int = Query(default=50, ge=1, le=200),
) -> InvestigationListResponse:
    records = investigation_service.investigation_repository.list_open(
        db,
        limit=limit,
    )

    return InvestigationListResponse(
        investigations=records,
        total=len(records),
    )


@router.get("/investigations/{investigation_id}", response_model=InvestigationRead)
def get_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationRead:
    investigation = investigation_service.get_investigation(
        db,
        investigation_id,
    )

    if investigation is None:
        raise NotFoundError(f"Investigation not found: {investigation_id}")

    return investigation


@router.get(
    "/investigations/{investigation_id}/summary",
    response_model=InvestigationSummaryResponse,
)
def get_investigation_summary(
    investigation_id: str,
    db: Session = Depends(get_db),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationSummaryResponse:
    summary = investigation_service.get_investigation_summary(
        db,
        investigation_id,
    )

    if summary is None:
        raise NotFoundError(f"Investigation not found: {investigation_id}")

    return InvestigationSummaryResponse(**summary)