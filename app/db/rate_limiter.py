import time

import redis

from app.core.config import settings


class RateLimiter:
    """Per-tenant fixed-window rate limiter backed by Redis.

    One counter per (tenant, current minute) via INCR + EXPIRE. Cheap and
    atomic enough for abuse protection; not a precise sliding window.
    """

    WINDOW_SECONDS = 60

    def __init__(self, limit_per_minute: int | None = None) -> None:
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        self.limit = (
            settings.rate_limit_per_minute if limit_per_minute is None else limit_per_minute
        )

    def check(self, key: str, limit: int | None = None) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds). retry_after is 0 when allowed.

        `key` namespaces the counter (a tenant id, or e.g. "auth:<ip>"); `limit`
        overrides the default per-minute limit for this call."""
        effective_limit = self.limit if limit is None else limit
        if effective_limit <= 0:  # disabled
            return True, 0

        window = int(time.time()) // self.WINDOW_SECONDS
        redis_key = f"rl:{key}:{window}"
        count = self._redis.incr(redis_key)
        if count == 1:
            self._redis.expire(redis_key, self.WINDOW_SECONDS)
        if count > effective_limit:
            retry_after = self.WINDOW_SECONDS - (int(time.time()) % self.WINDOW_SECONDS)
            return False, retry_after
        return True, 0
