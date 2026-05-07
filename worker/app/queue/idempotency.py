import redis


class IdempotencyStore:
    def __init__(
        self,
        *,
        redis_client: redis.Redis,
        ttl_seconds: int,
    ):
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds

    def completed_key(
        self,
        idempotency_key: str,
    ) -> str:
        return f"worker:idempotency:completed:{idempotency_key}"

    def lock_key(
        self,
        idempotency_key: str,
    ) -> str:
        return f"worker:idempotency:lock:{idempotency_key}"

    def was_completed(
        self,
        idempotency_key: str,
    ) -> bool:
        return bool(self.redis_client.exists(self.completed_key(idempotency_key)))

    def mark_completed(
        self,
        idempotency_key: str,
        *,
        job_id: str,
    ) -> None:
        self.redis_client.set(
            self.completed_key(idempotency_key),
            job_id,
            ex=self.ttl_seconds,
        )

    def acquire_lock(
        self,
        idempotency_key: str,
        *,
        job_id: str,
        lock_ttl_seconds: int = 60 * 30,
    ) -> bool:
        return bool(
            self.redis_client.set(
                self.lock_key(idempotency_key),
                job_id,
                nx=True,
                ex=lock_ttl_seconds,
            )
        )

    def release_lock(
        self,
        idempotency_key: str,
    ) -> None:
        self.redis_client.delete(self.lock_key(idempotency_key))