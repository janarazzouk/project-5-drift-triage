from datetime import datetime

import redis
from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.db import check_db_connection
from app.core.deps import get_redis_client
from app.schemas.health import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(
    settings: Settings = Depends(get_settings),
    redis_client: redis.Redis = Depends(get_redis_client),
) -> HealthResponse:
    database_connected = False
    redis_connected = False

    try:
        database_connected = check_db_connection(settings)
    except Exception:
        database_connected = False

    try:
        redis_connected = bool(redis_client.ping())
    except Exception:
        redis_connected = False

    status = "ok" if database_connected and redis_connected else "degraded"

    return HealthResponse(
        service=settings.service_name,
        version=settings.service_version,
        status=status,
        database_connected=database_connected,
        redis_connected=redis_connected,
        timestamp=datetime.utcnow(),
    )