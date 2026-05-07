import json
import time
from datetime import datetime, timezone
from typing import Any

import redis
from pydantic import ValidationError

from app.clients.agent_client import AgentClient
from app.core.config import Settings
from app.core.errors import InvalidJobError
from app.core.logging import get_logger
from app.jobs.job_router import JobRouter
from app.queue.dlq import DeadLetterQueue
from app.queue.idempotency import IdempotencyStore
from app.queue.producer import QueueProducer
from app.queue.retry import RetryPolicy
from app.schemas.job import JobResultPayload, WorkerJobEnvelope
from app.services.job_log_service import JobLogService


logger = get_logger(__name__)


class QueueConsumer:
    def __init__(
        self,
        *,
        settings: Settings,
        redis_client: redis.Redis,
        job_router: JobRouter,
        retry_policy: RetryPolicy,
        queue_producer: QueueProducer,
        dlq: DeadLetterQueue,
        idempotency_store: IdempotencyStore,
        agent_client: AgentClient,
        job_log_service: JobLogService,
    ):
        self.settings = settings
        self.redis_client = redis_client
        self.job_router = job_router
        self.retry_policy = retry_policy
        self.queue_producer = queue_producer
        self.dlq = dlq
        self.idempotency_store = idempotency_store
        self.agent_client = agent_client
        self.job_log_service = job_log_service
        self._running = True

    def run_forever(self) -> None:
        logger.info(
            "Worker is listening for Redis jobs.",
            extra={"queue_name": self.settings.queue_name},
        )

        while self._running:
            try:
                processed = self.process_once()

                if not processed:
                    time.sleep(self.settings.worker_idle_sleep_seconds)

            except KeyboardInterrupt:
                logger.info("Worker stopped by keyboard interrupt.")
                self._running = False

            except Exception as exc:
                logger.exception(
                    "Unexpected worker loop error.",
                    extra={"error": str(exc)},
                )
                time.sleep(self.settings.worker_idle_sleep_seconds)

    def process_once(self) -> bool:
        raw_message = self.redis_client.brpoplpush(
            self.settings.queue_name,
            self.settings.queue_processing_name,
            timeout=self.settings.worker_poll_timeout_seconds,
        )

        if raw_message is None:
            return False

        try:
            envelope = self._parse_message(raw_message)
            self._process_envelope(envelope)
        finally:
            self.redis_client.lrem(
                self.settings.queue_processing_name,
                1,
                raw_message,
            )

        return True

    def _parse_message(
        self,
        raw_message: str,
    ) -> WorkerJobEnvelope:
        try:
            data = json.loads(raw_message)
            return WorkerJobEnvelope(**data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise InvalidJobError(f"Invalid job envelope: {exc}") from exc

    def _process_envelope(
        self,
        job: WorkerJobEnvelope,
    ) -> None:
        attempts = job.attempts + 1

        logger.info(
            "Processing job.",
            extra={
                "job_id": job.job_id,
                "job_type": job.job_type,
                "attempts": job.attempts,
            },
        )

        if self.idempotency_store.was_completed(job.idempotency_key):
            self.job_log_service.mark_skipped_duplicate(job)

            logger.info(
                "Skipping completed duplicate job.",
                extra={
                    "job_id": job.job_id,
                    "idempotency_key": job.idempotency_key,
                },
            )
            return

        lock_acquired = self.idempotency_store.acquire_lock(
            job.idempotency_key,
            job_id=job.job_id,
        )

        if not lock_acquired:
            logger.warning(
                "Could not acquire idempotency lock. Re-queuing job.",
                extra={
                    "job_id": job.job_id,
                    "idempotency_key": job.idempotency_key,
                },
            )

            self.queue_producer.requeue(job.model_dump(mode="json"))
            return

        self.job_log_service.mark_processing(
            job,
            attempts=attempts,
        )

        try:
            tool_result = self.job_router.run(job)

            if tool_result.success:
                self.idempotency_store.mark_completed(
                    job.idempotency_key,
                    job_id=job.job_id,
                )

                self._notify_agent(
                    job=job,
                    status="completed",
                    attempts=attempts,
                    result=tool_result.result,
                    error_message=None,
                )

                self.job_log_service.mark_completed(
                    job,
                    result=tool_result.result,
                    attempts=attempts,
                )

                logger.info(
                    "Job completed.",
                    extra={
                        "job_id": job.job_id,
                        "job_type": job.job_type,
                    },
                )
                return

            raise RuntimeError(tool_result.error_message or "Tool returned failure.")

        except Exception as exc:
            error_message = str(exc)

            logger.warning(
                "Job failed.",
                extra={
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "attempts": attempts,
                    "error": error_message,
                },
            )

            if self.retry_policy.should_retry(
                attempts,
                max_attempts=job.max_attempts,
            ):
                self.job_log_service.mark_retrying(
                    job,
                    error_message=error_message,
                    attempts=attempts,
                )

                delay_seconds = self.retry_policy.delay_seconds(attempts)

                logger.info(
                    "Retrying job after delay.",
                    extra={
                        "job_id": job.job_id,
                        "delay_seconds": delay_seconds,
                    },
                )

                time.sleep(delay_seconds)

                envelope = job.model_dump(mode="json")
                envelope["attempts"] = attempts
                envelope["last_error"] = error_message

                self.queue_producer.requeue(envelope)
                return

            envelope = job.model_dump(mode="json")
            envelope["attempts"] = attempts
            envelope["last_error"] = error_message

            self.dlq.send(
                envelope=envelope,
                error_message=error_message,
            )

            self._notify_agent(
                job=job,
                status="dlq",
                attempts=attempts,
                result=None,
                error_message=error_message,
            )

            self.job_log_service.mark_dlq(
                job,
                error_message=error_message,
                attempts=attempts,
            )

            logger.error(
                "Job moved to DLQ.",
                extra={
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "error": error_message,
                },
            )

        finally:
            self.idempotency_store.release_lock(job.idempotency_key)

    def _notify_agent(
        self,
        *,
        job: WorkerJobEnvelope,
        status: str,
        attempts: int,
        result: dict[str, Any] | None,
        error_message: str | None,
    ) -> None:
        payload = JobResultPayload(
            job_id=job.job_id,
            idempotency_key=job.idempotency_key,
            investigation_id=job.investigation_id,
            job_type=job.job_type,
            status=status,
            result=result,
            error_message=error_message,
            attempts=attempts,
            finished_at=datetime.now(timezone.utc),
        )

        self.agent_client.send_job_result(payload)