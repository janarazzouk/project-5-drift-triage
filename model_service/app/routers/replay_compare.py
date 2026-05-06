from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.dependencies import get_predictor
from app.schemas.replay_compare import ReplayComparisonResponse
from app.services.prediction_service import Predictor
from app.services.replay_service import compare_replay_fixture


router = APIRouter(tags=["replay"])


@router.get("/replay-fixture/compare", response_model=ReplayComparisonResponse)
def replay_fixture_compare(
    settings: Settings = Depends(get_settings),
    predictor: Predictor = Depends(get_predictor),
) -> ReplayComparisonResponse:
    result = compare_replay_fixture(settings, predictor)

    return ReplayComparisonResponse(**result)