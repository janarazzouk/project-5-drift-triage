from typing import Any

from sqlalchemy.orm import Session

from app.contracts.drift_webhook import DriftWebhookPayload, DriftWebhookResponse
from app.core.config import Settings
from app.core.logging import get_logger
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.drift_event_repository import DriftEventRepository
from app.services.approval_service import ApprovalService
from app.services.checkpoint_service import CheckpointService
from app.services.dashboard_event_service import DashboardEventService
from app.services.investigation_service import InvestigationService
from app.services.queue_service import QueueService


logger = get_logger(__name__)


class WebhookService:
    def __init__(
        self,
        *,
        settings: Settings,
        queue_service: QueueService,
        investigation_service: InvestigationService,
        approval_service: ApprovalService,
        dashboard_event_service: DashboardEventService,
        checkpoint_service: CheckpointService,
    ):
        self.settings = settings
        self.queue_service = queue_service
        self.investigation_service = investigation_service
        self.approval_service = approval_service
        self.dashboard_event_service = dashboard_event_service
        self.checkpoint_service = checkpoint_service

        self.drift_event_repository = DriftEventRepository()
        self.message_repository = AgentMessageRepository()

    def process_drift_webhook(
        self,
        db: Session,
        payload: DriftWebhookPayload,
    ) -> DriftWebhookResponse:
        existing_event = self.drift_event_repository.get_by_event_id(
            db,
            payload.event_id,
        )

        if existing_event is not None:
            investigation = self.investigation_service.get_by_event_id(
                db,
                payload.event_id,
            )

            return DriftWebhookResponse(
                accepted=True,
                duplicate=True,
                event_id=payload.event_id,
                investigation_id=investigation.id if investigation else None,
                message="Duplicate event ignored.",
            )

        drift_event = self.drift_event_repository.create_from_webhook(
            db,
            payload,
        )

        investigation = self.investigation_service.create_from_drift_event(
            db,
            drift_event,
        )

        self.dashboard_event_service.emit_event(
            event_type="investigation.created",
            payload={
                "investigation_id": investigation.id,
                "event_id": drift_event.event_id,
                "severity": drift_event.new_severity,
                "model_name": drift_event.model_name,
                "model_version": drift_event.model_version,
            },
        )

        try:
            self._run_agent_flow(
                db,
                investigation_id=investigation.id,
            )
        except Exception as exc:
            logger.exception(
                "Agent flow failed after drift webhook.",
                extra={
                    "event_id": payload.event_id,
                    "investigation_id": investigation.id,
                },
            )

            self.investigation_service.fail(
                db,
                investigation_id=investigation.id,
                summary=f"Agent flow failed: {exc}",
                result={"error": str(exc)},
                state=investigation.state_json,
            )

        return DriftWebhookResponse(
            accepted=True,
            duplicate=False,
            event_id=payload.event_id,
            investigation_id=investigation.id,
            message="Drift event accepted and investigation started.",
        )

    def _run_agent_flow(
        self,
        db: Session,
        *,
        investigation_id: str,
    ) -> None:
        investigation = self.investigation_service.get_investigation(
            db,
            investigation_id,
        )

        if investigation is None:
            raise ValueError(f"Investigation not found: {investigation_id}")

        initial_state = investigation.state_json

        from app.agents.graph import run_investigation_graph

        final_state = run_investigation_graph(
            settings=self.settings,
            checkpoint_service=self.checkpoint_service,
            initial_state=initial_state,
            graph_thread_id=investigation.graph_thread_id,
        )

        self.investigation_service.update_after_agent_run(
            db,
            investigation_id=investigation_id,
            state=final_state,
        )

        self._apply_agent_decision(
            db,
            investigation_id=investigation_id,
            state=final_state,
        )

    def _apply_agent_decision(
        self,
        db: Session,
        *,
        investigation_id: str,
        state: dict[str, Any],
    ) -> None:
        recommended_action = state.get("recommended_action")
        production_action_required = bool(
            state.get("production_action_required", False)
        )
        queue_job_required = bool(state.get("queue_job_required", False))
        summary = state.get("summary") or "Agent completed investigation."

        if production_action_required:
            approval = self.approval_service.create_approval(
                db,
                investigation_id=investigation_id,
                requested_action=recommended_action or "unknown",
                target_environment="production",
                model_name=state["model_name"],
                model_version=state.get("model_version"),
                reason=summary,
                request_payload=state,
            )

            state["approval_id"] = approval.id
            state["status"] = "waiting_for_approval"
            state["current_step"] = "waiting_for_approval"

            self.investigation_service.mark_waiting_for_approval(
                db,
                investigation_id=investigation_id,
                approval_id=approval.id,
                recommended_action=recommended_action or "unknown",
                state=state,
            )

            self.dashboard_event_service.emit_event(
                event_type="approval.created",
                payload={
                    "approval_id": approval.id,
                    "investigation_id": investigation_id,
                    "requested_action": recommended_action,
                },
            )

            return

        if queue_job_required and recommended_action:
            enqueue_response = self.queue_service.enqueue_job(
                db,
                investigation_id=investigation_id,
                job_type=recommended_action,
                payload={
                    "investigation_id": investigation_id,
                    "event_id": state.get("event_id"),
                    "model_name": state.get("model_name"),
                    "model_version": state.get("model_version"),
                    "severity": state.get("severity"),
                    "drift_report": state.get("drift_report"),
                    "recommended_action": recommended_action,
                },
                idempotency_key=(
                    f"{recommended_action}:{investigation_id}:"
                    f"{state.get('model_version') or 'unknown'}"
                ),
            )

            queued_job_ids = list(state.get("queued_job_ids") or [])

            if not enqueue_response.duplicate:
                queued_job_ids.append(enqueue_response.job_id)

            state["queued_job_ids"] = queued_job_ids
            state["status"] = "waiting_for_job"
            state["current_step"] = "waiting_for_job"

            self.investigation_service.mark_waiting_for_job(
                db,
                investigation_id=investigation_id,
                recommended_action=recommended_action,
                state=state,
            )

            self.dashboard_event_service.emit_event(
                event_type="job.queued",
                payload={
                    "job_id": enqueue_response.job_id,
                    "investigation_id": investigation_id,
                    "job_type": recommended_action,
                    "duplicate": enqueue_response.duplicate,
                },
            )

            return

        if recommended_action in {"monitor", "resolve", None}:
            state["status"] = "resolved"
            state["current_step"] = "completed"

            self.investigation_service.resolve(
                db,
                investigation_id=investigation_id,
                summary=summary,
                result={
                    "recommended_action": recommended_action,
                    "production_action_required": production_action_required,
                    "queue_job_required": queue_job_required,
                },
                state=state,
            )

            self.dashboard_event_service.emit_event(
                event_type="investigation.resolved",
                payload={
                    "investigation_id": investigation_id,
                    "recommended_action": recommended_action,
                },
            )