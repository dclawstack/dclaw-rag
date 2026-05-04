import json
from typing import Any

import redis

from app.core.config import settings


class Cache:
    def __init__(self) -> None:
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    def get(self, key: str) -> Any | None:
        raw = self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        self._redis.setex(key, ttl, json.dumps(value, default=str))

    def delete(self, key: str) -> None:
        self._redis.delete(key)
