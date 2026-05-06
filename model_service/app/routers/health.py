from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.dependencies import get_predictor
from app.schemas.health import HealthResponse
from app.services.prediction_service import Predictor


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_settings),
    predictor: Predictor = Depends(get_predictor),
) -> HealthResponse:
    return HealthResponse(
        service=settings.service_name,
        version=settings.service_version,
        status="ok",
        model_loaded=predictor.model is not None,
        timestamp=datetime.utcnow(),
    )