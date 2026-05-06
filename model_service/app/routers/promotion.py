from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_promotion_service
from app.schemas.promotion import (
    PromotionChecklistResponse,
    PromotionRequest,
    PromotionResponse,
)
from app.services.promotion_service import PromotionService


router = APIRouter(tags=["promotion"])


@router.get("/promotion/checklist", response_model=PromotionChecklistResponse)
def promotion_checklist(
    db: Session = Depends(get_db),
    promotion_service: PromotionService = Depends(get_promotion_service),
) -> PromotionChecklistResponse:
    return promotion_service.run_checklist(db)


@router.post(
    "/promotion/production",
    response_model=PromotionResponse,
    responses={409: {"model": PromotionResponse}},
)
def promote_to_production(
    payload: PromotionRequest,
    db: Session = Depends(get_db),
    promotion_service: PromotionService = Depends(get_promotion_service),
):
    response = promotion_service.request_production_promotion(
        db=db,
        request=payload,
    )

    if not response.promoted:
        return JSONResponse(
            status_code=409,
            content=response.model_dump(mode="json"),
        )

    return response