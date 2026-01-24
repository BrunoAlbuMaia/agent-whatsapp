# Infrastructure/data/redis/context/redis_context.py
import redis
from src.config import settings

class RedisContext:
    _client = None  # singleton simples

    @classmethod
    def get_client(cls) -> redis.Redis:
        if settings.REDIS_URL:
            cls._client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                retry_on_timeout=True,
                socket_timeout=5,
                health_check_interval=30
            )
        return cls._client
