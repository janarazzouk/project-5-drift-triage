from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.drift_event import DriftEvent
from app.models.investigation import Investigation
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.investigation_repository import InvestigationRepository
from app.repositories.job_repository import JobRepository


class InvestigationService:
    def __init__(self):
        self.investigation_repository = InvestigationRepository()
        self.message_repository = AgentMessageRepository()
        self.job_repository = JobRepository()
        self.approval_repository = ApprovalRepository()

    def create_from_drift_event(
        self,
        db: Session,
        drift_event: DriftEvent,
    ) -> Investigation:
        existing = self.investigation_repository.get_by_event_id(
            db,
            drift_event.event_id,
        )

        if existing is not None:
            return existing

        investigation_id = f"inv_{uuid4().hex[:12]}"
        graph_thread_id = f"thread_{investigation_id}"

        state = {
            "investigation_id": investigation_id,
            "event_id": drift_event.event_id,
            "model_name": drift_event.model_name,
            "model_version": drift_event.model_version,
            "previous_severity": drift_event.previous_severity,
            "new_severity": drift_event.new_severity,
            "severity": drift_event.new_severity,
            "overall_score": drift_event.overall_score,
            "sample_size": drift_event.sample_size,
            "min_required_samples": drift_event.min_required_samples,
            "drift_report": drift_event.drift_report_json,
            "metadata": drift_event.metadata_json or {},
            "current_step": "created",
            "status": "open",
            "recommended_action": None,
            "production_action_required": False,
            "queue_job_required": False,
            "queued_job_ids": [],
            "approval_id": None,
            "summary": None,
            "messages": [],
        }

        investigation = self.investigation_repository.create(
            db,
            investigation_id=investigation_id,
            event_id=drift_event.event_id,
            model_name=drift_event.model_name,
            model_version=drift_event.model_version,
            severity=drift_event.new_severity,
            graph_thread_id=graph_thread_id,
            state=state,
        )

        self.message_repository.create_system_message(
            db,
            investigation_id=investigation.id,
            content=(
                f"Investigation {investigation.id} opened for drift event "
                f"{drift_event.event_id}. Severity changed from "
                f"{drift_event.previous_severity} to {drift_event.new_severity}."
            ),
            node_name="webhook",
            metadata={
                "event_id": drift_event.event_id,
                "model_name": drift_event.model_name,
                "model_version": drift_event.model_version,
            },
        )

        return investigation

    def get_investigation(
        self,
        db: Session,
        investigation_id: str,
    ) -> Investigation | None:
        return self.investigation_repository.get_by_id(db, investigation_id)

    def get_by_event_id(
        self,
        db: Session,
        event_id: str,
    ) -> Investigation | None:
        return self.investigation_repository.get_by_event_id(db, event_id)

    def list_investigations(
        self,
        db: Session,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[Investigation], int]:
        records = self.investigation_repository.list_recent(
            db,
            limit=limit,
            offset=offset,
            status=status,
        )
        total = self.investigation_repository.count(db, status=status)

        return records, total

    def get_investigation_summary(
        self,
        db: Session,
        investigation_id: str,
    ) -> dict[str, Any] | None:
        investigation = self.investigation_repository.get_by_id(
            db,
            investigation_id,
        )

        if investigation is None:
            return None

        messages = self.message_repository.list_by_investigation(
            db,
            investigation_id,
        )
        jobs = self.job_repository.list_by_investigation(
            db,
            investigation_id,
        )
        approvals = self.approval_repository.list_by_investigation(
            db,
            investigation_id,
        )

        return {
            "investigation": investigation,
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "node_name": message.node_name,
                    "message_type": message.message_type,
                    "content": message.content,
                    "metadata_json": message.metadata_json,
                    "created_at": message.created_at,
                }
                for message in messages
            ],
            "jobs": [
                {
                    "id": job.id,
                    "job_id": job.job_id,
                    "idempotency_key": job.idempotency_key,
                    "job_type": job.job_type,
                    "status": job.status,
                    "payload_json": job.payload_json,
                    "result_json": job.result_json,
                    "error_message": job.error_message,
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                    "queued_at": job.queued_at,
                    "started_at": job.started_at,
                    "finished_at": job.finished_at,
                    "sent_to_dlq": job.sent_to_dlq,
                    "dlq_reason": job.dlq_reason,
                }
                for job in jobs
            ],
            "approvals": [
                {
                    "id": approval.id,
                    "requested_action": approval.requested_action,
                    "target_environment": approval.target_environment,
                    "status": approval.status,
                    "reason": approval.reason,
                    "approved": approval.approved,
                    "approved_by": approval.approved_by,
                    "approved_at": approval.approved_at,
                    "rejected_by": approval.rejected_by,
                    "rejected_at": approval.rejected_at,
                    "rejection_reason": approval.rejection_reason,
                }
                for approval in approvals
            ],
        }

    def update_after_agent_run(
        self,
        db: Session,
        *,
        investigation_id: str,
        state: dict[str, Any],
    ) -> Investigation | None:
        status = state.get("status")
        current_step = state.get("current_step")
        recommended_action = state.get("recommended_action")
        production_action_required = state.get("production_action_required")
        approval_id = state.get("approval_id")
        summary = state.get("summary")

        return self.investigation_repository.update_state(
            db,
            investigation_id=investigation_id,
            status=status,
            current_step=current_step,
            recommended_action=recommended_action,
            production_action_required=production_action_required,
            approval_id=approval_id,
            summary=summary,
            state=state,
        )

    def mark_waiting_for_job(
        self,
        db: Session,
        *,
        investigation_id: str,
        recommended_action: str,
        state: dict[str, Any],
    ) -> Investigation | None:
        return self.investigation_repository.mark_waiting_for_job(
            db,
            investigation_id=investigation_id,
            recommended_action=recommended_action,
            state=state,
        )

    def mark_waiting_for_approval(
        self,
        db: Session,
        *,
        investigation_id: str,
        approval_id: str,
        recommended_action: str,
        state: dict[str, Any],
    ) -> Investigation | None:
        return self.investigation_repository.mark_waiting_for_approval(
            db,
            investigation_id=investigation_id,
            approval_id=approval_id,
            recommended_action=recommended_action,
            state=state,
        )

    def resolve(
        self,
        db: Session,
        *,
        investigation_id: str,
        summary: str,
        result: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> Investigation | None:
        self.message_repository.create_agent_message(
            db,
            investigation_id=investigation_id,
            node_name="completion",
            message_type="resolution",
            content=summary,
            metadata=result,
        )

        return self.investigation_repository.resolve(
            db,
            investigation_id=investigation_id,
            summary=summary,
            result=result,
            state=state,
        )

    def fail(
        self,
        db: Session,
        *,
        investigation_id: str,
        summary: str,
        result: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
    ) -> Investigation | None:
        self.message_repository.create_agent_message(
            db,
            investigation_id=investigation_id,
            node_name="completion",
            message_type="failure",
            content=summary,
            metadata=result,
        )

        return self.investigation_repository.fail(
            db,
            investigation_id=investigation_id,
            summary=summary,
            result=result,
            state=state,
        )