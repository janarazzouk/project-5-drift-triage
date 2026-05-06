from functools import lru_cache
from typing import Generator

import redis
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.db import build_session_factory, get_db_session, init_db
from app.core.logging import configure_logging
from app.services.approval_service import ApprovalService
from app.services.checkpoint_service import CheckpointService
from app.services.dashboard_event_service import DashboardEventService
from app.services.investigation_service import InvestigationService
from app.services.model_service_client import ModelServiceClient
from app.services.queue_service import QueueService
from app.services.webhook_service import WebhookService


@lru_cache
def get_session_factory() -> sessionmaker:
    settings = get_settings()
    return build_session_factory(settings)


def get_db() -> Generator[Session, None, None]:
    session_factory = get_session_factory()
    yield from get_db_session(session_factory)


@lru_cache
def get_redis_client() -> redis.Redis:
    settings = get_settings()

    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )


@lru_cache
def get_model_service_client() -> ModelServiceClient:
    settings = get_settings()

    return ModelServiceClient(
        base_url=settings.model_service_url,
        timeout_seconds=settings.model_service_timeout_seconds,
    )


@lru_cache
def get_queue_service() -> QueueService:
    settings = get_settings()
    redis_client = get_redis_client()

    return QueueService(
        settings=settings,
        redis_client=redis_client,
    )


@lru_cache
def get_dashboard_event_service() -> DashboardEventService:
    settings = get_settings()

    return DashboardEventService(settings=settings)


@lru_cache
def get_checkpoint_service() -> CheckpointService:
    settings = get_settings()

    return CheckpointService(settings=settings)


@lru_cache
def get_investigation_service() -> InvestigationService:
    return InvestigationService()


@lru_cache
def get_approval_service() -> ApprovalService:
    settings = get_settings()

    return ApprovalService(settings=settings)


@lru_cache
def get_webhook_service() -> WebhookService:
    settings = get_settings()
    queue_service = get_queue_service()
    investigation_service = get_investigation_service()
    approval_service = get_approval_service()
    dashboard_event_service = get_dashboard_event_service()
    checkpoint_service = get_checkpoint_service()

    return WebhookService(
        settings=settings,
        queue_service=queue_service,
        investigation_service=investigation_service,
        approval_service=approval_service,
        dashboard_event_service=dashboard_event_service,
        checkpoint_service=checkpoint_service,
    )

def initialize_resources() -> None:
    settings = get_settings()

    configure_logging()

    init_db(settings)

    checkpoint_service = get_checkpoint_service()
    checkpoint_service.setup()