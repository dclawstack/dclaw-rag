"""LLM usage/cost metering.

Aggregate token/cost counters live in Prometheus (bounded cardinality — labelled
by model, not tenant). Per-tenant totals live in Redis (unbounded tenants, but a
plain counter each) for billing, queryable via GET /usage. The current tenant is
carried on a contextvar set by get_principal, so the gateways can attribute usage
without threading it through every call. Metering is best-effort — it never
fails a request."""

from contextvars import ContextVar

import structlog
from prometheus_client import Counter

from app.core.config import settings

logger = structlog.get_logger(__name__)

current_tenant: ContextVar[str | None] = ContextVar("current_tenant", default=None)

LLM_TOKENS = Counter("llm_tokens_total", "LLM tokens", ["model", "kind"])
LLM_COST_USD = Counter("llm_cost_usd_total", "Estimated LLM cost in USD", ["model"])

_usage_store = None


def _store():
    global _usage_store
    if _usage_store is None:
        from app.db.usage_store import UsageStore

        _usage_store = UsageStore()
    return _usage_store


def record(model: str, prompt_tokens: int, completion_tokens: int) -> None:
    """Record one LLM call's usage against the current tenant. Never raises."""
    cost = (
        prompt_tokens / 1000 * settings.llm_price_per_1k_input_usd
        + completion_tokens / 1000 * settings.llm_price_per_1k_output_usd
    )
    LLM_TOKENS.labels(model, "prompt").inc(prompt_tokens)
    LLM_TOKENS.labels(model, "completion").inc(completion_tokens)
    LLM_COST_USD.labels(model).inc(cost)

    tenant = current_tenant.get()
    if not tenant:
        return
    try:
        _store().record(tenant, prompt_tokens + completion_tokens, cost)
    except Exception as exc:  # metering must never break the request path
        logger.debug("usage_metering_failed", error=str(exc))
