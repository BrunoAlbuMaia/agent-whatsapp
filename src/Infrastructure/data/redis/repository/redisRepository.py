import json
from typing import Any, Optional
from src.Infrastructure import RedisContext
from src.Domain import IRedisRepository

class RedisRepository(IRedisRepository):

    def __init__(self):
        self.redis = RedisContext.get_client()

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None
    ) -> None:
        data = json.dumps(value)

        if ttl_seconds:
            self.redis.setex(key, ttl_seconds, data)
        else:
            self.redis.set(key, data)

    def get(self, key: str) -> Optional[Any]:
        value = self.redis.get(key)
        return json.loads(value) if value else None

    def update(self, key: str, value: Any) -> bool:
        if not self.redis.exists(key):
            return False

        ttl = self.redis.ttl(key)
        data = json.dumps(value)

        if ttl > 0:
            self.redis.setex(key, ttl, data)
        else:
            self.redis.set(key, data)

        return True

    def renew_ttl(self, key: str, ttl_seconds: int) -> bool:
        return self.redis.expire(key, ttl_seconds)

    def get_ttl(self, key: str) -> int:
        """
        Retornos:
        -2 -> chave não existe
        -1 -> chave existe sem TTL
        >=0 -> segundos restantes
        """
        return self.redis.ttl(key)

    def delete(self, key: str) -> None:
        self.redis.delete(key)
