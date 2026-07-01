from app.api.dependencies import get_usage_store
from app.api.main import app


class _FakeUsageStore:
    def get(self, tenant_id):
        return {"tokens": 4200, "cost_usd": 0.0731}


async def test_usage_endpoint_returns_tenant_totals(client):
    app.dependency_overrides[get_usage_store] = lambda: _FakeUsageStore()
    resp = await client.get("/api/v1/rag/usage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "test-tenant"  # from conftest auth
    assert body["tokens"] == 4200
    assert body["cost_usd"] == 0.0731
