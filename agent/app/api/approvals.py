from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import (
    get_approval_service,
    get_db,
    get_model_service_client,
    get_queue_service,
)
from app.core.errors import NotFoundError
from app.schemas.approval import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalListResponse,
    ApprovalRead,
    ApprovalRejectionRequest,
)
from app.services.approval_service import ApprovalService
from app.services.model_service_client import ModelServiceClient
from app.services.queue_service import QueueService


router = APIRouter(tags=["approvals"])


@router.get("/approvals", response_model=ApprovalListResponse)
def list_approvals(
    db: Session = Depends(get_db),
    approval_service: ApprovalService = Depends(get_approval_service),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
) -> ApprovalListResponse:
    approvals, total = approval_service.list_approvals(
        db,
        limit=limit,
        offset=offset,
        status=status,
    )

    return ApprovalListResponse(
        approvals=approvals,
        total=total,
    )


@router.get("/approvals/pending", response_model=ApprovalListResponse)
def list_pending_approvals(
    db: Session = Depends(get_db),
    approval_service: ApprovalService = Depends(get_approval_service),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ApprovalListResponse:
    approvals, total = approval_service.list_pending(
        db,
        limit=limit,
        offset=offset,
    )

    return ApprovalListResponse(
        approvals=approvals,
        total=total,
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalRead)
def get_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    approval_service: ApprovalService = Depends(get_approval_service),
) -> ApprovalRead:
    approval = approval_service.approval_repository.get_by_id(
        db,
        approval_id,
    )

    if approval is None:
        raise NotFoundError(f"Approval not found: {approval_id}")

    return approval


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalDecisionResponse)
def approve_action(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
    approval_service: ApprovalService = Depends(get_approval_service),
    model_service_client: ModelServiceClient = Depends(get_model_service_client),
    queue_service: QueueService = Depends(get_queue_service),
) -> ApprovalDecisionResponse:
    approval, side_effect_result = approval_service.approve(
        db,
        approval_id=approval_id,
        approved_by=payload.approved_by,
        note=payload.note,
        model_service_client=model_service_client,
        queue_service=queue_service,
    )

    return ApprovalDecisionResponse(
        approval=approval,
        investigation_id=approval.investigation_id,
        message=(
            "Approval accepted. "
            f"Side effect result: {side_effect_result}"
            if side_effect_result
            else "Approval accepted."
        ),
    )


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalDecisionResponse)
def reject_action(
    approval_id: str,
    payload: ApprovalRejectionRequest,
    db: Session = Depends(get_db),
    approval_service: ApprovalService = Depends(get_approval_service),
) -> ApprovalDecisionResponse:
    approval = approval_service.reject(
        db,
        approval_id=approval_id,
        rejected_by=payload.rejected_by,
        rejection_reason=payload.rejection_reason,
    )

    return ApprovalDecisionResponse(
        approval=approval,
        investigation_id=approval.investigation_id,
        message="Approval rejected. Production action will not run.",
    )