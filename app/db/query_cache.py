import hashlib
import json

import redis

from app.core.config import settings


class QueryCache:
    """Tenant-scoped cache of query responses in Redis.

    Keys embed a per-tenant version counter; bumping it (on ingestion) makes all
    of that tenant's cached answers unreachable at once — instant invalidation
    without scanning, on top of the TTL.
    """

    def __init__(self) -> None:
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        self._ttl = settings.query_cache_ttl_seconds

    def _version(self, tenant_id: str) -> str:
        return str(self._redis.get(f"qcache_ver:{tenant_id}") or "0")

    def bump_version(self, tenant_id: str) -> None:
        self._redis.incr(f"qcache_ver:{tenant_id}")

    def _key(self, tenant_id: str, params: dict) -> str:
        blob = json.dumps(params, sort_keys=True)
        digest = hashlib.sha256(blob.encode()).hexdigest()
        return f"qcache:{tenant_id}:{self._version(tenant_id)}:{digest}"

    def get(self, tenant_id: str, params: dict) -> dict | None:
        if self._ttl <= 0:
            return None
        raw = self._redis.get(self._key(tenant_id, params))
        return json.loads(raw) if raw else None

    def set(self, tenant_id: str, params: dict, value: dict) -> None:
        if self._ttl <= 0:
            return
        self._redis.set(self._key(tenant_id, params), json.dumps(value), ex=self._ttl)
