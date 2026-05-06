from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import save_drift_check, save_or_update_reference_statistics
from app.core.dependencies import (
    get_db,
    get_drift_service,
    get_predictor,
    get_registry_client,
)
from app.schemas.drift import DriftResponse
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
) -> DriftResponse:
    registry_info = registry_client.get_model_info()

    save_or_update_reference_statistics(
        db,
        model_name=registry_info["model_name"],
        model_version=predictor.model_version,
        stats=drift_service.reference_stats,
    )

    result = drift_service.analyze(db)

    save_drift_check(
        db,
        sample_size=result["sample_size"],
        overall_score=result["overall_score"],
        severity=result["severity"],
        details=result,
    )

    return DriftResponse(**result)