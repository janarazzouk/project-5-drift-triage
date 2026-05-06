from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.replay_fixture import ReplayFixtureResponse
from app.services.replay_service import load_replay_fixture


router = APIRouter(tags=["replay"])


@router.get("/replay-fixture", response_model=ReplayFixtureResponse)
def replay_fixture(
    settings: Settings = Depends(get_settings),
) -> ReplayFixtureResponse:
    fixture = load_replay_fixture(settings)

    return ReplayFixtureResponse(fixture=fixture)