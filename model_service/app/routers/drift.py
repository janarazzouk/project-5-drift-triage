from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import (
    get_latest_drift_check,
    save_drift_check,
    save_or_update_reference_statistics,
)
from app.core.dependencies import (
    get_agent_webhook_service,
    get_db,
    get_drift_service,
    get_predictor,
    get_registry_client,
)
from app.schemas.drift import DriftResponse
from app.schemas.drift_webhook import DriftWebhookPayload
from app.services.agent_webhook_service import AgentWebhookService
from app.services.drift_service import DriftService
from app.services.prediction_service import Predictor
from app.services.registry_service import RegistryClient


router = APIRouter(tags=["drift"])


@router.get("/drift", response_model=DriftResponse)
def drift(
    db: Session = Depends(get_db),
    predictor: Predictor = Depends(get_predictor),
    registry_client: RegistryClient = Depends(get_registry_client),
    drift_service: DriftService = Depends(get_drift_service),
    agent_webhook_service: AgentWebhookService = Depends(get_agent_webhook_service),
) -> DriftResponse:
    previous_drift_check = get_latest_drift_check(db)

    registry_info = registry_client.get_model_info()

    save_or_update_reference_statistics(
        db,
        model_name=registry_info["model_name"],
        model_version=predictor.model_version,
        stats=drift_service.reference_stats,
    )

    result = drift_service.analyze(db)

    saved_drift_check = save_drift_check(
        db,
        sample_size=result["sample_size"],
        overall_score=result["overall_score"],
        severity=result["severity"],
        details=result,
    )

    if (
        previous_drift_check is not None
        and previous_drift_check.severity != result["severity"]
    ):
        webhook_payload = DriftWebhookPayload(
            event_id=f"drift_check_{saved_drift_check.id}_severity_changed",
            created_at=datetime.now(timezone.utc),
            model_name=registry_info["model_name"],
            model_version=registry_info["model_version"],
            previous_severity=previous_drift_check.severity,
            new_severity=result["severity"],
            overall_score=result["overall_score"],
            sample_size=result["sample_size"],
            min_required_samples=result["min_required_samples"],
            drift_report=result,
            metadata={
                "triggered_by": "/drift",
                "drift_check_id": saved_drift_check.id,
                "previous_drift_check_id": previous_drift_check.id,
                "environment": "local",
            },
        )

        agent_webhook_service.send_drift_severity_changed(webhook_payload)

    return DriftResponse(**result)