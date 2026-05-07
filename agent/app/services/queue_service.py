import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import redis
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import QueueError
from app.repositories.agent_message_repository import AgentMessageRepository
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.investigation_repository import InvestigationRepository
from app.repositories.job_repository import JobRepository
from app.schemas.queue import (
    EnqueueJobResponse,
    JobResultCallbackRequest,
    JobResultCallbackResponse,
    QueueStatusResponse,
)


class QueueService:
    def __init__(
        self,
        *,
        settings: Settings,
        redis_client: redis.Redis,
    ):
        self.settings = settings
        self.redis_client = redis_client
        self.job_repository = JobRepository()
        self.message_repository = AgentMessageRepository()
        self.investigation_repository = InvestigationRepository()
        self.approval_repository = ApprovalRepository()

    def enqueue_job(
        self,
        db: Session,
        *,
        investigation_id: str,
        job_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> EnqueueJobResponse:
        job_id = f"job_{uuid4().hex[:12]}"
        idempotency_key = (
            idempotency_key
            or f"{job_type}:{investigation_id}:{payload.get('model_version', 'unknown')}"
        )

        job_record, duplicate = self.job_repository.create_if_not_exists(
            db,
            job_id=job_id,
            idempotency_key=idempotency_key,
            investigation_id=investigation_id,
            job_type=job_type,
            payload=payload,
            max_attempts=self.settings.job_max_attempts,
        )

        if duplicate:
            return EnqueueJobResponse(
                queued=False,
                duplicate=True,
                job_id=job_record.job_id,
                idempotency_key=job_record.idempotency_key,
                message="Duplicate job was not re-queued.",
            )

        envelope = {
            "job_id": job_record.job_id,
            "idempotency_key": job_record.idempotency_key,
            "investigation_id": investigation_id,
            "job_type": job_type,
            "payload": payload,
            "attempts": 0,
            "max_attempts": self.settings.job_max_attempts,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            self.redis_client.lpush(
                self.settings.queue_name,
                json.dumps(envelope),
            )
        except redis.RedisError as exc:
            self.job_repository.mark_failed(
                db,
                job_id=job_record.job_id,
                error_message=str(exc),
            )

            raise QueueError(f"Failed to enqueue job in Redis: {exc}") from exc

        self.message_repository.create_system_message(
            db,
            investigation_id=investigation_id,
            node_name="queue",
            content=f"Queued {job_type} job {job_record.job_id}.",
            metadata={
                "job_id": job_record.job_id,
                "idempotency_key": job_record.idempotency_key,
                "job_type": job_type,
            },
        )

        return EnqueueJobResponse(
            queued=True,
            duplicate=False,
            job_id=job_record.job_id,
            idempotency_key=job_record.idempotency_key,
            message="Job queued successfully.",
        )

    def get_queue_status(
        self,
        db: Session,
        *,
        limit: int = 50,
    ) -> QueueStatusResponse:
        pending_count = int(self.redis_client.llen(self.settings.queue_name))
        processing_count = int(
            self.redis_client.llen(self.settings.queue_processing_name)
        )
        dlq_count = int(self.redis_client.llen(self.settings.queue_dlq_name))

        tracked_jobs = self.job_repository.list_recent(db, limit=limit)

        return QueueStatusResponse(
            queue_name=self.settings.queue_name,
            pending_count=pending_count,
            processing_count=processing_count,
            dlq_count=dlq_count,
            tracked_jobs=tracked_jobs,
        )

    def record_job_result(
        self,
        db: Session,
        payload: JobResultCallbackRequest,
    ) -> JobResultCallbackResponse:
        if payload.status == "completed":
            record = self.job_repository.mark_completed(
                db,
                job_id=payload.job_id,
                result=payload.result,
                attempts=payload.attempts,
            )
            content = f"Job {payload.job_id} completed."
        elif payload.status == "dlq":
            record = self.job_repository.mark_dlq(
                db,
                job_id=payload.job_id,
                reason=payload.error_message or "Job moved to DLQ.",
                attempts=payload.attempts,
                result=payload.result,
            )
            content = f"Job {payload.job_id} moved to DLQ."
        else:
            record = self.job_repository.mark_failed(
                db,
                job_id=payload.job_id,
                error_message=payload.error_message or "Job failed.",
                attempts=payload.attempts,
            )
            content = f"Job {payload.job_id} failed."

        if record is None:
            raise QueueError(f"Unknown job_id: {payload.job_id}")

        self.message_repository.create_tool_message(
            db,
            investigation_id=payload.investigation_id,
            node_name=payload.job_type,
            content=content,
            metadata={
                "job_id": payload.job_id,
                "job_type": payload.job_type,
                "status": payload.status,
                "result": payload.result,
                "error_message": payload.error_message,
            },
        )

        self._update_investigation_after_job_result(
            db=db,
            payload=payload,
        )

        return JobResultCallbackResponse(
            accepted=True,
            job_id=payload.job_id,
            investigation_id=payload.investigation_id,
            message="Job result recorded.",
        )

    def _update_investigation_after_job_result(
        self,
        *,
        db: Session,
        payload: JobResultCallbackRequest,
    ) -> None:
        investigation = self.investigation_repository.get_by_id(
            db,
            payload.investigation_id,
        )

        if investigation is None:
            return

        state = dict(investigation.state_json or {})
        state["last_job_result"] = {
            "job_id": payload.job_id,
            "job_type": payload.job_type,
            "status": payload.status,
            "result": payload.result,
            "error_message": payload.error_message,
            "attempts": payload.attempts,
            "finished_at": payload.finished_at.isoformat(),
        }

        if payload.status == "completed":
            if payload.job_type == "replay_test":
                self._handle_completed_replay_test(
                    db=db,
                    payload=payload,
                    state=state,
                )
                return

            if payload.job_type == "retrain":
                self._handle_completed_retrain(
                    db=db,
                    payload=payload,
                    state=state,
                )
                return

            if payload.job_type == "rollback":
                self._handle_completed_rollback(
                    db=db,
                    payload=payload,
                    state=state,
                )
                return

        if payload.status == "dlq":
            summary = (
                f"Job {payload.job_id} was moved to DLQ after retries. "
                f"Reason: {payload.error_message or 'Unknown error'}"
            )

            state["status"] = "failed"
            state["current_step"] = "job_dlq"
            state["summary"] = summary

            self.investigation_repository.fail(
                db,
                investigation_id=payload.investigation_id,
                summary=summary,
                result=state["last_job_result"],
                state=state,
            )
            return

        if payload.status == "failed":
            summary = (
                f"Job {payload.job_id} failed. "
                f"Reason: {payload.error_message or 'Unknown error'}"
            )

            state["status"] = "failed"
            state["current_step"] = "job_failed"
            state["summary"] = summary

            self.investigation_repository.fail(
                db,
                investigation_id=payload.investigation_id,
                summary=summary,
                result=state["last_job_result"],
                state=state,
            )

    def _handle_completed_replay_test(
        self,
        *,
        db: Session,
        payload: JobResultCallbackRequest,
        state: dict[str, Any],
    ) -> None:
        replay_passed = bool((payload.result or {}).get("passed"))

        if replay_passed:
            summary = (
                "Replay test completed successfully. The current model service "
                "matches the saved replay fixture, so no immediate Production "
                "change is required."
            )

            state["status"] = "resolved"
            state["current_step"] = "replay_test_completed"
            state["summary"] = summary

            self.investigation_repository.resolve(
                db,
                investigation_id=payload.investigation_id,
                summary=summary,
                result=state["last_job_result"],
                state=state,
            )
            return

        summary = (
            "Replay test completed but failed. The model output does not match "
            "the saved replay fixture. Further investigation or retraining is needed."
        )

        state["status"] = "failed"
        state["current_step"] = "replay_test_failed"
        state["summary"] = summary

        self.investigation_repository.fail(
            db,
            investigation_id=payload.investigation_id,
            summary=summary,
            result=state["last_job_result"],
            state=state,
        )

    def _handle_completed_retrain(
        self,
        *,
        db: Session,
        payload: JobResultCallbackRequest,
        state: dict[str, Any],
    ) -> None:
        result = payload.result or {}

        if not bool(result.get("completed")):
            summary = (
                "Retrain job completed at the queue level, but the retrain result "
                "does not say completed=true. Review the worker result."
            )
            state["status"] = "failed"
            state["current_step"] = "retrain_result_invalid"
            state["summary"] = summary

            self.investigation_repository.fail(
                db,
                investigation_id=payload.investigation_id,
                summary=summary,
                result=state["last_job_result"],
                state=state,
            )
            return

        candidate_model_version = _optional_string(result.get("model_version"))
        candidate_model_name = (
            result.get("registered_model_name")
            or state.get("model_name")
            or "unknown"
        )

        if candidate_model_version is None:
            summary = (
                "Retrain job completed, but the worker did not return a candidate "
                "model_version, so promotion approval cannot be created."
            )
            state["status"] = "failed"
            state["current_step"] = "candidate_model_missing"
            state["summary"] = summary

            self.investigation_repository.fail(
                db,
                investigation_id=payload.investigation_id,
                summary=summary,
                result=state["last_job_result"],
                state=state,
            )
            return

        state["candidate_model"] = {
            "model_name": candidate_model_name,
            "model_version": candidate_model_version,
            "mlflow_run_id": result.get("mlflow_run_id"),
            "mlflow_model_uri": result.get("mlflow_model_uri"),
            "artifact_dir": result.get("artifact_dir"),
            "selected_threshold": result.get("selected_threshold"),
            "test_metrics": result.get("test_metrics") or {},
            "training_summary_path": result.get("training_summary_path"),
        }

        approval = self._create_promotion_approval_after_retrain(
            db=db,
            payload=payload,
            state=state,
            candidate_model_name=candidate_model_name,
            candidate_model_version=candidate_model_version,
        )

        if approval is None:
            summary = (
                "Retrain job completed and a promotion approval already exists for "
                f"candidate model version {candidate_model_version}."
            )
            approvals = self.approval_repository.list_by_investigation(
                db,
                payload.investigation_id,
            )
            existing = next(
                (
                    item
                    for item in approvals
                    if item.requested_action == "promote_to_production"
                    and item.model_version == candidate_model_version
                ),
                None,
            )
            approval_id = existing.id if existing else state.get("promotion_approval_id")
        else:
            summary = (
                "Retrain job completed. A new candidate model is available and "
                "human approval is required before Production promotion."
            )
            approval_id = approval.id

        state["status"] = "waiting_for_approval"
        state["current_step"] = "promotion_approval_pending"
        state["recommended_action"] = "promote_to_production"
        state["production_action_required"] = True
        state["approval_status"] = "pending"
        state["promotion_approval_id"] = approval_id
        state["approval_id"] = approval_id
        state["summary"] = summary

        self.investigation_repository.update_state(
            db,
            investigation_id=payload.investigation_id,
            status="waiting_for_approval",
            current_step="promotion_approval_pending",
            recommended_action="promote_to_production",
            production_action_required=True,
            approval_id=approval_id,
            summary=summary,
            result=state["last_job_result"],
            state=state,
        )

    def _create_promotion_approval_after_retrain(
        self,
        *,
        db: Session,
        payload: JobResultCallbackRequest,
        state: dict[str, Any],
        candidate_model_name: str,
        candidate_model_version: str,
    ):
        existing_approval = self._find_existing_promotion_approval(
            db=db,
            investigation_id=payload.investigation_id,
            model_version=candidate_model_version,
        )

        if existing_approval is not None:
            return None

        approval_id = f"approval_{uuid4().hex[:12]}"
        reason = (
            "Retraining completed and produced candidate model version "
            f"{candidate_model_version}. Approve this request to run the model "
            "service promotion checklist and promote the candidate to Production "
            "only if the checklist passes."
        )

        request_payload = {
            **state,
            "candidate_model": state.get("candidate_model"),
            "requested_action": "promote_to_production",
            "target_environment": "production",
            "source_retrain_job_id": payload.job_id,
        }

        approval = self.approval_repository.create(
            db,
            approval_id=approval_id,
            investigation_id=payload.investigation_id,
            requested_action="promote_to_production",
            target_environment="production",
            model_name=candidate_model_name,
            model_version=candidate_model_version,
            reason=reason,
            request_payload=request_payload,
        )

        self.message_repository.create_system_message(
            db,
            investigation_id=payload.investigation_id,
            node_name="approval",
            content=(
                "Human approval requested to promote candidate model version "
                f"{candidate_model_version} to Production."
            ),
            metadata={
                "approval_id": approval.id,
                "requested_action": approval.requested_action,
                "target_environment": approval.target_environment,
                "model_name": approval.model_name,
                "model_version": approval.model_version,
            },
        )

        return approval

    def _find_existing_promotion_approval(
        self,
        *,
        db: Session,
        investigation_id: str,
        model_version: str,
    ):
        approvals = self.approval_repository.list_by_investigation(
            db,
            investigation_id,
        )

        for approval in approvals:
            if (
                approval.requested_action == "promote_to_production"
                and approval.model_version == model_version
                and approval.status in {"pending", "approved"}
            ):
                return approval

        return None

    def _handle_completed_rollback(
        self,
        *,
        db: Session,
        payload: JobResultCallbackRequest,
        state: dict[str, Any],
    ) -> None:
        summary = "Rollback job completed."

        state["status"] = "resolved"
        state["current_step"] = "rollback_completed"
        state["summary"] = summary

        self.investigation_repository.resolve(
            db,
            investigation_id=payload.investigation_id,
            summary=summary,
            result=state["last_job_result"],
            state=state,
        )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None

    return str(value)