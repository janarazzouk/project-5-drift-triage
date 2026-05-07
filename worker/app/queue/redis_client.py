import redis

from app.core.config import Settings


def build_redis_client(settings: Settings) -> redis.Redis:
    return redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )