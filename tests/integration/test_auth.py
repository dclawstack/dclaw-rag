from uuid import uuid4

from app.api.dependencies import (
    Principal,
    get_api_key_store,
    get_collection_store,
    get_pipeline,
    get_principal,
    get_store,
)
from app.api.main import app
from app.core.config import settings


class _KeyStore:
    def __init__(self, mapping):
        self._m = mapping

    def get(self, raw_key):
        return self._m.get(raw_key)

    def create(self, tenant_id, name=""):
        return "sk_minted", {"tenant_id": tenant_id, "name": name}


def _unauth():
    # drop the conftest auto-auth so the real get_principal runs
    app.dependency_overrides.pop(get_principal, None)


# --- authentication (on /system, which only depends on the principal) ---


async def test_missing_key_returns_401(client):
    _unauth()
    resp = await client.get("/api/v1/rag/system")
    assert resp.status_code == 401


async def test_invalid_key_returns_401(client):
    _unauth()
    app.dependency_overrides[get_api_key_store] = lambda: _KeyStore({})
    resp = await client.get("/api/v1/rag/system", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


async def test_valid_key_is_accepted(client):
    _unauth()
    app.dependency_overrides[get_api_key_store] = lambda: _KeyStore(
        {"sk_good": {"tenant_id": "acme", "name": "k"}}
    )
    resp = await client.get("/api/v1/rag/system", headers={"Authorization": "Bearer sk_good"})
    assert resp.status_code == 200


# --- admin-only key minting ---


async def test_create_key_requires_admin(client):
    app.dependency_overrides[get_api_key_store] = lambda: _KeyStore({})
    resp = await client.post("/api/v1/rag/keys", json={"tenant_id": "acme"})
    assert resp.status_code == 403


async def test_create_key_with_admin_returns_a_key(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_api_key", "admin-secret")
    app.dependency_overrides[get_api_key_store] = lambda: _KeyStore({})
    resp = await client.post(
        "/api/v1/rag/keys",
        json={"tenant_id": "acme", "name": "x"},
        headers={"X-Admin-Key": "admin-secret"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["api_key"] == "sk_minted"
    assert body["tenant_id"] == "acme"


# --- tenant isolation ---


class _ColStore:
    def __init__(self):
        self._d = {}

    def create(self, cid, record):
        self._d[cid] = record
        return record

    def get(self, cid, tenant):
        r = self._d.get(cid)
        return r if r and r["tenant_id"] == tenant else None

    def list(self, tenant):
        return [r for r in self._d.values() if r["tenant_id"] == tenant]

    def delete(self, cid, tenant):
        if self.get(cid, tenant) is None:
            return False
        del self._d[cid]
        return True


class _Qdrant:
    def count_points(self, filters=None):
        return 0

    def list_documents(self, filters=None, limit=1000):
        return []


async def test_tenant_cannot_see_or_delete_another_tenants_collection(client):
    store = _ColStore()
    app.dependency_overrides[get_collection_store] = lambda: store
    app.dependency_overrides[get_store] = lambda: _Qdrant()

    app.dependency_overrides[get_principal] = lambda: Principal(tenant_id="A")
    created = (await client.post("/api/v1/rag/collections", json={"name": "A-secret"})).json()

    app.dependency_overrides[get_principal] = lambda: Principal(tenant_id="B")
    assert (await client.get("/api/v1/rag/collections")).json() == []  # B sees nothing
    assert (await client.delete(f"/api/v1/rag/collections/{created['id']}")).status_code == 404


# --- client cannot spoof tenant on ingest ---


class _CapturingPipeline:
    def __init__(self):
        self.request = None

    def ingest_text(self, text, request):
        self.request = request
        return uuid4(), 1


async def test_client_supplied_tenant_id_is_ignored(client):
    pipeline = _CapturingPipeline()
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    app.dependency_overrides[get_principal] = lambda: Principal(tenant_id="real-tenant")

    resp = await client.post(
        "/api/v1/rag/documents/text",
        json={"text": "hi", "metadata": {"tenant_id": "evil-tenant"}},
    )

    assert resp.status_code == 200
    assert pipeline.request.tenant_id == "real-tenant"  # principal wins over the body
