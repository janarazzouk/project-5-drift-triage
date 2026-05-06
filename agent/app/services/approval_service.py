from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.contracts.promotion import (
    HumanApproval,
    PromotionDriftContext,
    PromotionRequestPayload,
)
from app.core.config import Settings
from app.core.errors import InvalidStateError, NotFoundError
from app.models.approval import Approval
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.investigation_repository import InvestigationRepository
from app.services.model_service_client import ModelServiceClient
from app.services.queue_service import QueueService


class ApprovalService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.approval_repository = ApprovalRepository()
        self.investigation_repository = InvestigationRepository()
        self.message_repository = AgentMessageRepository()

    def create_approval(
        self,
        db: Session,
        *,
        investigation_id: str,
        requested_action: str,
        target_environment: str,
        model_name: str,
        model_version: str | None,
        reason: str,
        request_payload: dict[str, Any] | None = None,
    ) -> Approval:
        approval_id = f"approval_{uuid4().hex[:12]}"

        approval = self.approval_repository.create(
            db,
            approval_id=approval_id,
            investigation_id=investigation_id,
            requested_action=requested_action,
            target_environment=target_environment,
            model_name=model_name,
            model_version=model_version,
            reason=reason,
            request_payload=request_payload,
        )

        self.message_repository.create_system_message(
            db,
            investigation_id=investigation_id,
            node_name="approval",
            content=(
                f"Human approval requested for action '{requested_action}' "
                f"on model version '{model_version}'."
            ),
            metadata={
                "approval_id": approval.id,
                "requested_action": requested_action,
                "target_environment": target_environment,
            },
        )

        return approval

    def list_approvals(
        self,
        db: Session,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[Approval], int]:
        records = self.approval_repository.list_recent(
            db,
            limit=limit,
            offset=offset,
            status=status,
        )
        total = self.approval_repository.count(db, status=status)

        return records, total

    def list_pending(
        self,
        db: Session,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Approval], int]:
        records = self.approval_repository.list_pending(
            db,
            limit=limit,
            offset=offset,
        )
        total = self.approval_repository.count(db, status="pending")

        return records, total

    def approve(
        self,
        db: Session,
        *,
        approval_id: str,
        approved_by: str,
        note: str | None = None,
        model_service_client: ModelServiceClient | None = None,
        queue_service: QueueService | None = None,
    ) -> tuple[Approval, dict[str, Any] | None]:
        approval = self.approval_repository.get_by_id(db, approval_id)

        if approval is None:
            raise NotFoundError(f"Approval not found: {approval_id}")

        if approval.status != "pending":
            raise InvalidStateError(
                f"Approval {approval_id} is not pending. Current status: {approval.status}"
            )

        decision_payload = {
            "approved_by": approved_by,
            "note": note,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }

        approval = self.approval_repository.approve(
            db,
            approval_id=approval_id,
            approved_by=approved_by,
            decision_payload=decision_payload,
        )

        self.message_repository.create_system_message(
            db,
            investigation_id=approval.investigation_id,
            node_name="approval",
            content=f"Approval {approval.id} approved by {approved_by}.",
            metadata=decision_payload,
        )

        side_effect_result: dict[str, Any] | None = None

        if approval.requested_action == "promote_to_production":
            if model_service_client is None:
                raise InvalidStateError(
                    "ModelServiceClient is required for promote_to_production."
                )

            side_effect_result = self._call_promotion_endpoint(
                db,
                approval=approval,
                approved_by=approved_by,
                model_service_client=model_service_client,
            )

        elif approval.requested_action == "rollback_production":
            if queue_service is None:
                raise InvalidStateError(
                    "QueueService is required for rollback_production."
                )

            side_effect_result = self._queue_rollback_job(
                db,
                approval=approval,
                queue_service=queue_service,
            )

        return approval, side_effect_result

    def reject(
        self,
        db: Session,
        *,
        approval_id: str,
        rejected_by: str,
        rejection_reason: str,
    ) -> Approval:
        approval = self.approval_repository.get_by_id(db, approval_id)

        if approval is None:
            raise NotFoundError(f"Approval not found: {approval_id}")

        if approval.status != "pending":
            raise InvalidStateError(
                f"Approval {approval_id} is not pending. Current status: {approval.status}"
            )

        decision_payload = {
            "rejected_by": rejected_by,
            "rejection_reason": rejection_reason,
            "rejected_at": datetime.now(timezone.utc).isoformat(),
        }

        approval = self.approval_repository.reject(
            db,
            approval_id=approval_id,
            rejected_by=rejected_by,
            rejection_reason=rejection_reason,
            decision_payload=decision_payload,
        )

        self.message_repository.create_system_message(
            db,
            investigation_id=approval.investigation_id,
            node_name="approval",
            content=f"Approval {approval.id} rejected by {rejected_by}.",
            metadata=decision_payload,
        )

        self.investigation_repository.update_state(
            db,
            investigation_id=approval.investigation_id,
            status="resolved",
            current_step="approval_rejected",
            summary=(
                f"Production action '{approval.requested_action}' was rejected. "
                f"Reason: {rejection_reason}"
            ),
            result=decision_payload,
        )

        return approval

    def _call_promotion_endpoint(
        self,
        db: Session,
        *,
        approval: Approval,
        approved_by: str,
        model_service_client: ModelServiceClient,
    ) -> dict[str, Any]:
        investigation = self.investigation_repository.get_by_id(
            db,
            approval.investigation_id,
        )

        if investigation is None:
            raise NotFoundError(
                f"Investigation not found: {approval.investigation_id}"
            )

        state = investigation.state_json or {}

        request_id = (
            f"promotion_{approval.investigation_id}_"
            f"{approval.model_version or 'unknown'}_production"
        )

        drift_context = None

        if state.get("event_id") and state.get("severity"):
            drift_context = PromotionDriftContext(
                event_id=state["event_id"],
                severity=state["severity"],
                previous_model_version=state.get("previous_model_version"),
            )

        payload = PromotionRequestPayload(
            request_id=request_id,
            created_at=datetime.now(timezone.utc),
            investigation_id=approval.investigation_id,
            approval_id=approval.id,
            model_name=approval.model_name,
            model_version=approval.model_version or "",
            human_approval=HumanApproval(
                approved=True,
                approved_by=approved_by,
                approved_at=datetime.now(timezone.utc),
                approval_source="dashboard",
            ),
            reason=approval.reason,
            drift_context=drift_context,
            metadata={
                "agent_investigation_id": approval.investigation_id,
                "approval_id": approval.id,
            },
        )

        result = model_service_client.request_production_promotion(payload)

        if result.get("promoted"):
            status = "resolved"
            current_step = "promotion_completed"
            summary = (
                f"Model version {approval.model_version} was promoted to Production."
            )
        else:
            status = "failed"
            current_step = "promotion_blocked"
            summary = (
                f"Promotion was blocked by the model service checklist: "
                f"{result.get('message', 'No message returned.')}"
            )

        self.investigation_repository.update_state(
            db,
            investigation_id=approval.investigation_id,
            status=status,
            current_step=current_step,
            summary=summary,
            result=result,
        )

        self.message_repository.create_tool_message(
            db,
            investigation_id=approval.investigation_id,
            node_name="promotion",
            content=summary,
            metadata=result,
        )

        return result

    def _queue_rollback_job(
        self,
        db: Session,
        *,
        approval: Approval,
        queue_service: QueueService,
    ) -> dict[str, Any]:
        payload = {
            "investigation_id": approval.investigation_id,
            "approval_id": approval.id,
            "model_name": approval.model_name,
            "model_version": approval.model_version,
            "target_environment": approval.target_environment,
            "requested_action": approval.requested_action,
        }

        response = queue_service.enqueue_job(
            db,
            investigation_id=approval.investigation_id,
            job_type="rollback",
            payload=payload,
            idempotency_key=(
                f"rollback:{approval.investigation_id}:"
                f"{approval.model_version or 'unknown'}"
            ),
        )

        self.investigation_repository.update_state(
            db,
            investigation_id=approval.investigation_id,
            status="waiting_for_job",
            current_step="rollback_queued",
            recommended_action="rollback_production",
            production_action_required=True,
        )

        return response.model_dump(mode="json")