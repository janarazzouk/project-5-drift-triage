from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_rollback_service
from app.schemas.rollback import RollbackRequest, RollbackResponse
from app.services.rollback_service import RollbackService


router = APIRouter(tags=["rollback"])


@router.post(
    "/rollback/production",
    response_model=RollbackResponse,
    responses={409: {"model": RollbackResponse}},
)
def rollback_production(
    payload: RollbackRequest,
    db: Session = Depends(get_db),
    rollback_service: RollbackService = Depends(get_rollback_service),
):
    response = rollback_service.rollback_production(
        db=db,
        request=payload,
    )

    if not response.rolled_back:
        return JSONResponse(
            status_code=409,
            content=response.model_dump(mode="json"),
        )

    return response