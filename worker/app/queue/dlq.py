import json
from datetime import datetime, timezone
from typing import Any

import redis

from app.core.config import Settings


class DeadLetterQueue:
    def __init__(
        self,
        *,
        settings: Settings,
        redis_client: redis.Redis,
    ):
        self.settings = settings
        self.redis_client = redis_client

    def send(
        self,
        *,
        envelope: dict[str, Any],
        error_message: str,
    ) -> None:
        dlq_payload = {
            "job": envelope,
            "error_message": error_message,
            "sent_to_dlq_at": datetime.now(timezone.utc).isoformat(),
        }

        self.redis_client.lpush(
            self.settings.queue_dlq_name,
            json.dumps(dlq_payload),
        )