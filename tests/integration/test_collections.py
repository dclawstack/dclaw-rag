from app.api.dependencies import get_collection_store, get_document_store, get_store
from app.api.main import app

BASE = "/api/v1/rag/collections"


class _FakeCollectionStore:
    def __init__(self):
        self._data = {}

    def create(self, collection_id, record):
        self._data[collection_id] = record
        return record

    def get(self, collection_id, tenant_id):
        record = self._data.get(collection_id)
        return record if record and record.get("tenant_id") == tenant_id else None

    def list(self, tenant_id):
        return [r for r in self._data.values() if r.get("tenant_id") == tenant_id]

    def delete(self, collection_id, tenant_id):
        if self.get(collection_id, tenant_id) is None:
            return False
        del self._data[collection_id]
        return True


class _FakeQdrant:
    def __init__(self, chunk_count=0):
        self._chunk_count = chunk_count

    def count_points(self, filters=None):
        return self._chunk_count


class _FakeDocStore:
    def __init__(self, docs=None):
        self._docs = docs or []

    def count(self, tenant_id, collection_id=None):
        return len(self._docs)

    def list(self, tenant_id, collection_id=None, limit=100, offset=0):
        return self._docs[offset : offset + limit]


def _use(store, qdrant, docs=None):
    app.dependency_overrides[get_collection_store] = lambda: store
    app.dependency_overrides[get_store] = lambda: qdrant
    app.dependency_overrides[get_document_store] = lambda: docs or _FakeDocStore()


async def test_create_then_list_collection(client):
    store = _FakeCollectionStore()
    _use(store, _FakeQdrant())

    resp = await client.post(BASE, json={"name": "Legal", "description": "contracts"})
    assert resp.status_code == 200
    created = resp.json()
    assert created["name"] == "Legal"
    assert created["id"]
    assert created["document_count"] == 0
    assert created["chunk_count"] == 0
    assert created["status"] == "ready"

    listed = (await client.get(BASE)).json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]


async def test_list_reports_live_counts(client):
    store = _FakeCollectionStore()
    docs = [{"id": "d1", "filename": "a.md", "status": "ready", "created_at": ""}]
    _use(store, _FakeQdrant(chunk_count=7), _FakeDocStore(docs))

    created = (await client.post(BASE, json={"name": "Docs"})).json()
    listed = (await client.get(BASE)).json()

    assert listed[0]["id"] == created["id"]
    assert listed[0]["chunk_count"] == 7  # from Qdrant (indexed count)
    assert listed[0]["document_count"] == 1  # from the registry


async def test_delete_collection(client):
    store = _FakeCollectionStore()
    _use(store, _FakeQdrant())

    created = (await client.post(BASE, json={"name": "Temp"})).json()
    cid = created["id"]

    assert (await client.delete(f"{BASE}/{cid}")).status_code == 200
    assert (await client.get(BASE)).json() == []
    # deleting again is a 404
    assert (await client.delete(f"{BASE}/{cid}")).status_code == 404


async def test_documents_404_for_unknown_collection(client):
    _use(_FakeCollectionStore(), _FakeQdrant())
    resp = await client.get(f"{BASE}/nope/documents")
    assert resp.status_code == 404


async def test_documents_listing_for_existing_collection(client):
    store = _FakeCollectionStore()
    docs = [{"id": "d1", "filename": "a.md", "status": "ready", "created_at": ""}]
    _use(store, _FakeQdrant(), _FakeDocStore(docs))

    cid = (await client.post(BASE, json={"name": "Docs"})).json()["id"]
    resp = await client.get(f"{BASE}/{cid}/documents")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["filename"] == "a.md"


async def test_documents_listing_honors_limit_and_offset(client):
    store = _FakeCollectionStore()
    docs = [
        {"id": f"d{i}", "filename": f"{i}.md", "status": "ready", "created_at": ""}
        for i in range(5)
    ]
    _use(store, _FakeQdrant(), _FakeDocStore(docs))

    cid = (await client.post(BASE, json={"name": "Docs"})).json()["id"]

    page = (await client.get(f"{BASE}/{cid}/documents?limit=2&offset=2")).json()
    assert [d["id"] for d in page] == ["d2", "d3"]

    # out-of-range params are rejected (bounded page size)
    assert (await client.get(f"{BASE}/{cid}/documents?limit=0")).status_code == 422
    assert (await client.get(f"{BASE}/{cid}/documents?limit=999")).status_code == 422
