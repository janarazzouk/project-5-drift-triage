from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import save_prediction
from app.core.dependencies import get_db, get_predictor
from app.schemas.predict import PredictionRequest, PredictionResponse
from app.services.prediction_service import Predictor


router = APIRouter(tags=["prediction"])


@router.post("/predict", response_model=PredictionResponse)
def predict(
    payload: PredictionRequest,
    db: Session = Depends(get_db),
    predictor: Predictor = Depends(get_predictor),
) -> PredictionResponse:
    try:
        result = predictor.predict(
            features=payload.features,
            request_id=payload.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    save_prediction(
        db,
        request_id=result["request_id"],
        features=result["features"],
        probability=result["probability"],
        predicted_class=result["predicted_class"],
        threshold=result["threshold"],
        model_version=result["model_version"],
    )

    return PredictionResponse(
        request_id=result["request_id"],
        probability=result["probability"],
        predicted_class=result["predicted_class"],
        threshold=result["threshold"],
        model_version=result["model_version"],
        saved=True,
    )