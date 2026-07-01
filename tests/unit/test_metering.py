from app.core import metering
from app.core.config import settings


class _RecordingStore:
    def __init__(self):
        self.calls = []

    def record(self, tenant_id, tokens, cost_usd):
        self.calls.append((tenant_id, tokens, cost_usd))


def test_record_computes_cost_and_attributes_to_current_tenant(monkeypatch):
    store = _RecordingStore()
    monkeypatch.setattr(metering, "_store", lambda: store)
    monkeypatch.setattr(settings, "llm_price_per_1k_input_usd", 0.01)
    monkeypatch.setattr(settings, "llm_price_per_1k_output_usd", 0.02)

    token = metering.current_tenant.set("acme")
    try:
        metering.record("some-model", prompt_tokens=1000, completion_tokens=500)
    finally:
        metering.current_tenant.reset(token)

    assert len(store.calls) == 1
    tenant, tokens, cost = store.calls[0]
    assert tenant == "acme"
    assert tokens == 1500
    assert cost == 1000 / 1000 * 0.01 + 500 / 1000 * 0.02  # 0.02


def test_record_without_tenant_does_not_touch_store(monkeypatch):
    store = _RecordingStore()
    monkeypatch.setattr(metering, "_store", lambda: store)
    metering.current_tenant.set(None)
    metering.record("m", 10, 10)
    assert store.calls == []


def test_record_never_raises_if_store_fails(monkeypatch):
    def _boom():
        raise RuntimeError("redis down")

    monkeypatch.setattr(metering, "_store", _boom)
    token = metering.current_tenant.set("acme")
    try:
        metering.record("m", 10, 10)  # must not raise
    finally:
        metering.current_tenant.reset(token)
