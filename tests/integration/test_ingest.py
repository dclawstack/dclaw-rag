import pytest

import app.api.routes.ingest as ingest_module
from app.api.dependencies import Principal, get_document_store, get_principal
from app.api.main import app

UPLOAD_PATH = "/api/v1/rag/documents/upload"
TEXT_PATH = "/api/v1/rag/documents/text"


class _FakeDocStore:
    def __init__(self):
        self.records = {}
        self._by_checksum = {}

    def find_by_checksum(self, tenant_id, checksum):
        doc_id = self._by_checksum.get((tenant_id, checksum))
        return self.records.get(doc_id)

    def create(self, record):
        self.records[record["id"]] = record
        if record.get("checksum"):
            self._by_checksum[(record["tenant_id"], record["checksum"])] = record["id"]
        return record

    def get(self, doc_id, tenant_id):
        rec = self.records.get(doc_id)
        return rec if rec and rec["tenant_id"] == tenant_id else None


@pytest.fixture
def store():
    s = _FakeDocStore()
    app.dependency_overrides[get_document_store] = lambda: s
    return s


@pytest.fixture
def enqueued(monkeypatch):
    """Spy on task dispatch so no broker is touched."""
    calls = []
    monkeypatch.setattr(
        ingest_module.ingest_document_task, "delay", lambda *a, **k: calls.append(a)
    )
    return calls


async def test_ingest_text_enqueues_pending(client, store, enqueued):
    resp = await client.post(
        TEXT_PATH,
        json={"text": "hello world", "metadata": {"source": "unit", "title": "t", "tags": ["a"]}},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"
    assert body["chunks_inserted"] == 0
    assert body["doc_id"]

    # a pending record was registered, and the heavy work was handed to the worker
    rec = store.records[body["doc_id"]]
    assert rec["status"] == "pending" and rec["source"] == "unit"
    assert len(enqueued) == 1
    doc_id, text, request_dict = enqueued[0]
    assert doc_id == body["doc_id"]
    assert text == "hello world"
    assert request_dict["source"] == "unit" and request_dict["tags"] == ["a"]


async def test_upload_extracts_then_enqueues(client, store, enqueued):
    files = {"file": ("notes.md", b"# Title\n\nbody text", "text/markdown")}
    data = {"metadata": '{"source": "unit"}'}
    resp = await client.post(UPLOAD_PATH, files=files, data=data)

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    assert len(enqueued) == 1
    _, text, request_dict = enqueued[0]
    assert "body text" in text  # extraction happened in-request
    assert request_dict["title"] == "notes.md"  # title falls back to filename


async def test_ingest_is_idempotent_by_checksum(client, store, enqueued):
    payload = {"text": "same content", "metadata": {"source": "unit"}}
    first = (await client.post(TEXT_PATH, json=payload)).json()
    second = (await client.post(TEXT_PATH, json=payload)).json()

    assert first["doc_id"] == second["doc_id"]  # deduped
    assert second["status"] == "pending"
    assert len(enqueued) == 1  # not re-enqueued


async def test_document_status_endpoint_is_tenant_scoped(client, store):
    store.create(
        {
            "id": "doc-1",
            "tenant_id": "test-tenant",
            "filename": "f",
            "status": "ready",
            "created_at": "",
            "chunk_count": 3,
            "error": None,
        }
    )

    ok = await client.get("/api/v1/rag/documents/doc-1")
    assert ok.status_code == 200
    assert ok.json()["status"] == "ready" and ok.json()["chunk_count"] == 3

    assert (await client.get("/api/v1/rag/documents/missing")).status_code == 404

    # another tenant cannot read it
    app.dependency_overrides[get_principal] = lambda: Principal(tenant_id="other")
    assert (await client.get("/api/v1/rag/documents/doc-1")).status_code == 404
