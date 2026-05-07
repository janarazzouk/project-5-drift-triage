from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import (
    get_existing_rollback_decision,
    get_registry_state,
    save_or_update_registry_state,
    save_rollback_decision,
)
from app.schemas.rollback import RollbackRequest, RollbackResponse
from app.services.registry_service import RegistryClient


class RollbackService:
    def __init__(
        self,
        settings: Settings,
        registry_client: RegistryClient,
    ):
        self.settings = settings
        self.registry_client = registry_client

    def rollback_production(
        self,
        db: Session,
        request: RollbackRequest,
    ) -> RollbackResponse:
        request_id = request.request_id or self._build_request_id(request)

        existing = get_existing_rollback_decision(
            db,
            request_id=request_id,
        )

        if existing is not None:
            return RollbackResponse(
                rolled_back=existing.rolled_back,
                duplicate=True,
                request_id=existing.request_id,
                investigation_id=existing.investigation_id,
                approval_id=existing.approval_id,
                model_name=existing.model_name,
                model_version=existing.model_version,
                target_environment=existing.target_environment,
                previous_stage=existing.previous_stage,
                new_stage=existing.new_stage,
                message=existing.message,
                details=existing.details_json,
                completed_at=existing.created_at,
            )

        registry_info = self.registry_client.get_model_info()

        loaded_model_name = registry_info["model_name"]
        loaded_model_version = registry_info["model_version"]

        target_model_version = request.model_version or loaded_model_version

        existing_registry_state = get_registry_state(
            db,
            model_name=request.model_name,
            model_version=target_model_version,
        )

        previous_stage = (
            existing_registry_state.model_stage
            if existing_registry_state is not None
            else None
        )

        validation_error = self._validate_request_against_loaded_model(
            request=request,
            loaded_model_name=loaded_model_name,
            loaded_model_version=loaded_model_version,
            target_model_version=target_model_version,
        )

        if validation_error is not None:
            details = {
                "validation_error": validation_error,
                "loaded_model_name": loaded_model_name,
                "loaded_model_version": loaded_model_version,
                "target_model_version": target_model_version,
                "note": (
                    "This local rollback endpoint only supports marking the currently "
                    "loaded model version as Production. It does not switch artifacts yet."
                ),
            }

            message = f"Rollback blocked: {validation_error}"

            save_rollback_decision(
                db,
                request_id=request_id,
                investigation_id=request.investigation_id,
                approval_id=request.approval_id,
                model_name=request.model_name,
                model_version=target_model_version,
                requested_action=request.requested_action,
                target_environment=request.target_environment,
                previous_stage=previous_stage,
                new_stage=previous_stage,
                rolled_back=False,
                message=message,
                details=details,
            )

            return RollbackResponse(
                rolled_back=False,
                duplicate=False,
                request_id=request_id,
                investigation_id=request.investigation_id,
                approval_id=request.approval_id,
                model_name=request.model_name,
                model_version=target_model_version,
                target_environment=request.target_environment,
                previous_stage=previous_stage,
                new_stage=previous_stage,
                message=message,
                details=details,
                completed_at=datetime.now(timezone.utc),
            )

        updated_registry_state = save_or_update_registry_state(
            db,
            model_name=request.model_name,
            model_version=target_model_version,
            model_stage="production",
            artifact_uri=registry_info["artifact_paths"].get("model"),
            selected_threshold=registry_info["threshold"],
            metrics=registry_info["metrics"],
        )

        details = {
            "registry_state_id": updated_registry_state.id,
            "artifact_uri": updated_registry_state.artifact_uri,
            "selected_threshold": updated_registry_state.selected_threshold,
            "loaded_model_name": loaded_model_name,
            "loaded_model_version": loaded_model_version,
            "target_model_version": target_model_version,
            "triggered_by_investigation_id": request.investigation_id,
            "triggered_by_approval_id": request.approval_id,
            "reason": request.reason,
            "metadata": request.metadata,
            "note": (
                "Rollback recorded successfully. In this local implementation, rollback "
                "marks the approved target version as Production in registry_state."
            ),
        }

        message = (
            f"Rollback completed. Model '{request.model_name}' version "
            f"'{target_model_version}' is now marked as Production."
        )

        save_rollback_decision(
            db,
            request_id=request_id,
            investigation_id=request.investigation_id,
            approval_id=request.approval_id,
            model_name=request.model_name,
            model_version=target_model_version,
            requested_action=request.requested_action,
            target_environment=request.target_environment,
            previous_stage=previous_stage,
            new_stage="production",
            rolled_back=True,
            message=message,
            details=details,
        )

        return RollbackResponse(
            rolled_back=True,
            duplicate=False,
            request_id=request_id,
            investigation_id=request.investigation_id,
            approval_id=request.approval_id,
            model_name=request.model_name,
            model_version=target_model_version,
            target_environment=request.target_environment,
            previous_stage=previous_stage,
            new_stage="production",
            message=message,
            details=details,
            completed_at=datetime.now(timezone.utc),
        )

    def _build_request_id(
        self,
        request: RollbackRequest,
    ) -> str:
        model_version = request.model_version or "unknown"

        return (
            f"rollback_{request.investigation_id}_"
            f"{request.approval_id}_{model_version}_production"
        )

    def _validate_request_against_loaded_model(
        self,
        *,
        request: RollbackRequest,
        loaded_model_name: str,
        loaded_model_version: str | None,
        target_model_version: str | None,
    ) -> str | None:
        if request.requested_action != "rollback_production":
            return "requested_action must be rollback_production."

        if request.target_environment != "production":
            return "target_environment must be production."

        if request.model_name != loaded_model_name:
            return (
                f"Requested model_name '{request.model_name}' does not match "
                f"loaded model_name '{loaded_model_name}'."
            )

        if loaded_model_version is not None and target_model_version is not None:
            if str(target_model_version) != str(loaded_model_version):
                return (
                    f"Requested model_version '{target_model_version}' does not match "
                    f"currently loaded model_version '{loaded_model_version}'."
                )

        return None