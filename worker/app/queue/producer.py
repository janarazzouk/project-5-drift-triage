import json
from typing import Any

import redis

from app.core.config import Settings


class QueueProducer:
    def __init__(
        self,
        *,
        settings: Settings,
        redis_client: redis.Redis,
    ):
        self.settings = settings
        self.redis_client = redis_client

    def requeue(
        self,
        envelope: dict[str, Any],
    ) -> None:
        self.redis_client.lpush(
            self.settings.queue_name,
            json.dumps(envelope),
        )