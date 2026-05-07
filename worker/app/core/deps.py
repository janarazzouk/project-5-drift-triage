from functools import lru_cache

from sqlalchemy.orm import sessionmaker

from app.clients.agent_client import AgentClient
from app.clients.model_service_client import ModelServiceClient
from app.core.config import get_settings
from app.core.db import build_session_factory, init_db
from app.jobs.job_router import JobRouter
from app.jobs.replay_test_job import ReplayTestJob
from app.jobs.retrain_job import RetrainJob
from app.jobs.rollback_job import RollbackJob
from app.queue.consumer import QueueConsumer
from app.queue.dlq import DeadLetterQueue
from app.queue.idempotency import IdempotencyStore
from app.queue.producer import QueueProducer
from app.queue.redis_client import build_redis_client
from app.queue.retry import RetryPolicy
from app.services.job_log_service import JobLogService
from app.tools.replay_test import ReplayTestTool
from app.tools.retrain import RetrainTool
from app.tools.rollback import RollbackTool


@lru_cache
def get_session_factory() -> sessionmaker:
    settings = get_settings()
    return build_session_factory(settings)


@lru_cache
def get_redis_client():
    settings = get_settings()
    return build_redis_client(settings)


@lru_cache
def get_agent_client() -> AgentClient:
    settings = get_settings()

    return AgentClient(
        base_url=settings.agent_url,
        timeout_seconds=settings.agent_timeout_seconds,
        result_path=settings.agent_job_result_path,
    )


@lru_cache
def get_model_service_client() -> ModelServiceClient:
    settings = get_settings()

    return ModelServiceClient(
        base_url=settings.model_service_url,
        timeout_seconds=settings.model_service_timeout_seconds,
        rollback_path=settings.rollback_endpoint_path,
    )


@lru_cache
def get_idempotency_store() -> IdempotencyStore:
    settings = get_settings()
    redis_client = get_redis_client()

    return IdempotencyStore(
        redis_client=redis_client,
        ttl_seconds=settings.job_idempotency_ttl_seconds,
    )


@lru_cache
def get_retry_policy() -> RetryPolicy:
    settings = get_settings()

    return RetryPolicy(
        max_attempts=settings.job_max_attempts,
        base_delay_seconds=settings.job_base_retry_delay_seconds,
    )


@lru_cache
def get_queue_producer() -> QueueProducer:
    settings = get_settings()
    redis_client = get_redis_client()

    return QueueProducer(
        settings=settings,
        redis_client=redis_client,
    )


@lru_cache
def get_dead_letter_queue() -> DeadLetterQueue:
    settings = get_settings()
    redis_client = get_redis_client()

    return DeadLetterQueue(
        settings=settings,
        redis_client=redis_client,
    )


@lru_cache
def get_job_log_service() -> JobLogService:
    return JobLogService(
        session_factory=get_session_factory(),
    )


@lru_cache
def get_job_router() -> JobRouter:
    settings = get_settings()
    model_service_client = get_model_service_client()

    replay_tool = ReplayTestTool(
        model_service_client=model_service_client,
    )

    retrain_tool = RetrainTool(
        command=settings.retrain_command,
        working_dir=settings.retrain_working_dir,
        timeout_seconds=settings.retrain_timeout_seconds,
    )

    rollback_tool = RollbackTool(
        model_service_client=model_service_client,
    )

    return JobRouter(
        handlers={
            "replay_test": ReplayTestJob(replay_tool),
            "retrain": RetrainJob(retrain_tool),
            "rollback": RollbackJob(rollback_tool),
        }
    )


@lru_cache
def get_consumer() -> QueueConsumer:
    settings = get_settings()
    redis_client = get_redis_client()

    return QueueConsumer(
        settings=settings,
        redis_client=redis_client,
        job_router=get_job_router(),
        retry_policy=get_retry_policy(),
        queue_producer=get_queue_producer(),
        dlq=get_dead_letter_queue(),
        idempotency_store=get_idempotency_store(),
        agent_client=get_agent_client(),
        job_log_service=get_job_log_service(),
    )


def initialize_resources() -> None:
    settings = get_settings()
    init_db(settings)