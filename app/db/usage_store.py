import redis

from app.core.config import settings


class UsageStore:
    """Per-tenant LLM usage totals in Redis (tokens + cost), for billing/metering."""

    def __init__(self) -> None:
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    def _tokens_key(self, tenant_id: str) -> str:
        return f"usage:{tenant_id}:tokens"

    def _cost_key(self, tenant_id: str) -> str:
        return f"usage:{tenant_id}:cost_usd"

    def record(self, tenant_id: str, tokens: int, cost_usd: float) -> None:
        self._redis.incrby(self._tokens_key(tenant_id), tokens)
        self._redis.incrbyfloat(self._cost_key(tenant_id), cost_usd)

    def get(self, tenant_id: str) -> dict:
        tokens = self._redis.get(self._tokens_key(tenant_id))
        cost = self._redis.get(self._cost_key(tenant_id))
        return {
            "tokens": int(tokens) if tokens else 0,
            "cost_usd": round(float(cost), 6) if cost else 0.0,
        }
