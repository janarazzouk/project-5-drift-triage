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

        self._mark_investigation_approval_approved(
            db,
            approval=approval,
            decision_payload=decision_payload,
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

        elif approval.requested_action == "retrain":
            if queue_service is None:
                raise InvalidStateError(
                    "QueueService is required for retrain approval."
                )

            side_effect_result = self._queue_retrain_job(
                db,
                approval=approval,
                approved_by=approved_by,
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

        investigation = self.investigation_repository.get_by_id(
            db,
            approval.investigation_id,
        )

        state = dict(investigation.state_json or {}) if investigation else {}

        summary = (
            f"Action '{approval.requested_action}' was rejected. "
            f"Reason: {rejection_reason}"
        )

        state["status"] = "resolved"
        state["current_step"] = "approval_rejected"
        state["approval_status"] = "rejected"
        state["summary"] = summary
        state["result"] = decision_payload

        self.investigation_repository.update_state(
            db,
            investigation_id=approval.investigation_id,
            status="resolved",
            current_step="approval_rejected",
            summary=summary,
            result=decision_payload,
            state=state,
        )

        return approval

    def _mark_investigation_approval_approved(
        self,
        db: Session,
        *,
        approval: Approval,
        decision_payload: dict[str, Any],
    ) -> None:
        investigation = self.investigation_repository.get_by_id(
            db,
            approval.investigation_id,
        )

        if investigation is None:
            return

        state = dict(investigation.state_json or {})
        state["approval_id"] = approval.id
        state["approval_status"] = "approved"
        state["status"] = "running"
        state["current_step"] = f"{approval.requested_action}_approved"
        state["result"] = decision_payload

        self.investigation_repository.update_state(
            db,
            investigation_id=approval.investigation_id,
            status="running",
            current_step=state["current_step"],
            approval_id=approval.id,
            result=decision_payload,
            state=state,
        )

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

        state = dict(investigation.state_json or {})
        request_payload = dict(approval.request_payload_json or {})

        request_id = (
            f"promotion_{approval.investigation_id}_"
            f"{approval.model_version or 'unknown'}_production"
        )

        drift_context = None
        event_id = state.get("event_id") or request_payload.get("event_id")
        severity = state.get("severity") or request_payload.get("severity")

        if event_id and severity:
            drift_context = PromotionDriftContext(
                event_id=event_id,
                severity=severity,
                previous_model_version=state.get("model_version"),
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
                "candidate_model": state.get("candidate_model"),
                "source": "approval_service",
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
                "Promotion was blocked by the model service checklist: "
                f"{result.get('message', 'No message returned.')}"
            )

        state["status"] = status
        state["current_step"] = current_step
        state["summary"] = summary
        state["approval_status"] = "approved"
        state["promotion_result"] = result
        state["promoted_model"] = {
            "model_name": approval.model_name,
            "model_version": approval.model_version,
            "target_environment": approval.target_environment,
            "promoted": bool(result.get("promoted")),
        }

        self.investigation_repository.update_state(
            db,
            investigation_id=approval.investigation_id,
            status=status,
            current_step=current_step,
            summary=summary,
            result=result,
            state=state,
        )

        self.message_repository.create_tool_message(
            db,
            investigation_id=approval.investigation_id,
            node_name="promotion",
            content=summary,
            metadata=result,
        )

        return result

    def _queue_retrain_job(
        self,
        db: Session,
        *,
        approval: Approval,
        approved_by: str,
        queue_service: QueueService,
    ) -> dict[str, Any]:
        investigation = self.investigation_repository.get_by_id(
            db,
            approval.investigation_id,
        )

        state = dict(investigation.state_json or {}) if investigation else {}
        request_payload = dict(approval.request_payload_json or {})

        model_version = approval.model_version or state.get("model_version")
        event_id = state.get("event_id") or request_payload.get("event_id")
        severity = state.get("severity") or request_payload.get("severity")
        drift_report = state.get("drift_report") or request_payload.get("drift_report")

        payload = {
            "investigation_id": approval.investigation_id,
            "approval_id": approval.id,
            "approved_by": approved_by,
            "model_name": approval.model_name,
            "model_version": model_version,
            "target_environment": approval.target_environment,
            "event_id": event_id,
            "severity": severity,
            "drift_report": drift_report,
            "recommended_action": "retrain",
            "requested_action": approval.requested_action,
        }

        response = queue_service.enqueue_job(
            db,
            investigation_id=approval.investigation_id,
            job_type="retrain",
            payload=payload,
            idempotency_key=(
                f"retrain:{approval.investigation_id}:"
                f"{model_version or 'unknown'}"
            ),
        )

        queued_job_ids = list(state.get("queued_job_ids") or [])

        if response.queued and not response.duplicate:
            queued_job_ids.append(response.job_id)

        state["status"] = "waiting_for_job"
        state["current_step"] = "retrain_queued"
        state["recommended_action"] = "retrain"
        state["production_action_required"] = True
        state["queue_job_required"] = True
        state["approval_id"] = approval.id
        state["approval_status"] = "approved"
        state["queued_job_ids"] = queued_job_ids
        state["last_queue_result"] = response.model_dump(mode="json")

        self.investigation_repository.update_state(
            db,
            investigation_id=approval.investigation_id,
            status="waiting_for_job",
            current_step="retrain_queued",
            recommended_action="retrain",
            production_action_required=True,
            approval_id=approval.id,
            state=state,
        )

        self.message_repository.create_system_message(
            db,
            investigation_id=approval.investigation_id,
            node_name="queue",
            content=(
                f"Retrain job {response.job_id} queued after human approval "
                f"{approval.id}."
            ),
            metadata=response.model_dump(mode="json"),
        )

        return response.model_dump(mode="json")

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

        investigation = self.investigation_repository.get_by_id(
            db,
            approval.investigation_id,
        )

        state = dict(investigation.state_json or {}) if investigation else {}

        queued_job_ids = list(state.get("queued_job_ids") or [])

        if response.queued and not response.duplicate:
            queued_job_ids.append(response.job_id)

        state["status"] = "waiting_for_job"
        state["current_step"] = "rollback_queued"
        state["recommended_action"] = "rollback_production"
        state["production_action_required"] = True
        state["approval_id"] = approval.id
        state["approval_status"] = "approved"
        state["queued_job_ids"] = queued_job_ids
        state["last_queue_result"] = response.model_dump(mode="json")

        self.investigation_repository.update_state(
            db,
            investigation_id=approval.investigation_id,
            status="waiting_for_job",
            current_step="rollback_queued",
            recommended_action="rollback_production",
            production_action_required=True,
            approval_id=approval.id,
            state=state,
        )

        return response.model_dump(mode="json")
