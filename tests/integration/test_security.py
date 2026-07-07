import app.api.routes.ingest as ingest_module
from app.api.dependencies import (
    get_document_store,
    get_llm,
    get_rate_limiter,
    get_searcher,
)
from app.api.main import app
from app.core.config import settings

TEXT_PATH = "/api/v1/rag/documents/text"


class _Limiter:
    def __init__(self, allowed: bool):
        self._allowed = allowed

    def check(self, key, limit=None):
        return (True, 0) if self._allowed else (False, 30)


class _DocStore:
    def __init__(self):
        self.records = {}

    def find_by_checksum(self, tenant_id, checksum):
        return None

    def create(self, record):
        self.records[record["id"]] = record
        return record


def _spy_enqueue(monkeypatch):
    calls = []
    monkeypatch.setattr(
        ingest_module, "dispatch_ingestion", lambda *a, **k: calls.append(a)
    )
    return calls


# --- security headers ---


async def test_security_headers_present(client):
    resp = await client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"


# --- rate limiting ---


async def test_rate_limit_blocks_with_429_and_retry_after(client):
    app.dependency_overrides[get_rate_limiter] = lambda: _Limiter(allowed=False)
    resp = await client.post(TEXT_PATH, json={"text": "hi"})
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "30"


async def test_rate_limit_allows_under_limit(client, monkeypatch):
    app.dependency_overrides[get_rate_limiter] = lambda: _Limiter(allowed=True)
    app.dependency_overrides[get_document_store] = lambda: _DocStore()
    _spy_enqueue(monkeypatch)
    resp = await client.post(TEXT_PATH, json={"text": "hello"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


# --- request body size cap (middleware) ---


async def test_oversized_body_rejected_with_413(client, monkeypatch):
    monkeypatch.setattr(settings, "max_request_bytes", 5)
    resp = await client.post(
        TEXT_PATH, json={"text": "this body is definitely longer than five bytes"}
    )
    assert resp.status_code == 413


# --- input validation ---


async def test_empty_text_rejected(client):
    app.dependency_overrides[get_rate_limiter] = lambda: _Limiter(allowed=True)
    resp = await client.post(TEXT_PATH, json={"text": ""})
    assert resp.status_code == 422


async def test_oversized_upload_rejected_with_413(client, monkeypatch):
    app.dependency_overrides[get_rate_limiter] = lambda: _Limiter(allowed=True)
    app.dependency_overrides[get_document_store] = lambda: _DocStore()
    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    files = {"file": ("big.txt", b"x" * 50, "text/plain")}
    resp = await client.post("/api/v1/rag/documents/upload", files=files)
    assert resp.status_code == 413


async def test_query_top_k_bounds_enforced(client):
    # keep heavy deps out; validation fails before the body runs
    app.dependency_overrides[get_rate_limiter] = lambda: _Limiter(allowed=True)
    app.dependency_overrides[get_searcher] = lambda: object()
    app.dependency_overrides[get_llm] = lambda: object()

    too_big = await client.post("/api/v1/rag/query", json={"question": "q", "top_k": 101})
    assert too_big.status_code == 422

    empty_q = await client.post("/api/v1/rag/query", json={"question": "", "top_k": 5})
    assert empty_q.status_code == 422
