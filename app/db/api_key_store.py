import hashlib
import json
import secrets

import redis

from app.core.config import settings


class ApiKeyStore:
    """Maps API keys to tenants, stored in Redis. Keys are stored hashed."""

    def __init__(self) -> None:
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    @staticmethod
    def _hash(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def _redis_key(self, raw_key: str) -> str:
        return f"apikey:{self._hash(raw_key)}"

    def get(self, raw_key: str) -> dict | None:
        data = self._redis.get(self._redis_key(raw_key))
        return json.loads(data) if data else None

    def create(self, tenant_id: str, name: str = "") -> tuple[str, dict]:
        raw_key = "sk_" + secrets.token_urlsafe(24)
        record = {"tenant_id": tenant_id, "name": name}
        self._redis.set(self._redis_key(raw_key), json.dumps(record))
        return raw_key, record

    def ensure_key(self, raw_key: str, tenant_id: str, name: str = "") -> None:
        """Idempotently seed a known key (used to bootstrap a dev key)."""
        redis_key = self._redis_key(raw_key)
        if not self._redis.exists(redis_key):
            self._redis.set(redis_key, json.dumps({"tenant_id": tenant_id, "name": name}))
