from app.api.dependencies import get_collection_store, get_store
from app.api.main import app

BASE = "/api/v1/rag/collections"


class _FakeCollectionStore:
    def __init__(self):
        self._data = {}

    def create(self, collection_id, record):
        self._data[collection_id] = record
        return record

    def get(self, collection_id):
        return self._data.get(collection_id)

    def list(self):
        return list(self._data.values())

    def delete(self, collection_id):
        return self._data.pop(collection_id, None) is not None


class _FakeQdrant:
    def __init__(self, chunk_count=0, docs=None):
        self._chunk_count = chunk_count
        self._docs = docs or []

    def count_points(self, filters=None):
        return self._chunk_count

    def list_documents(self, filters=None, limit=1000):
        return self._docs


def _use(store, qdrant):
    app.dependency_overrides[get_collection_store] = lambda: store
    app.dependency_overrides[get_store] = lambda: qdrant


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


async def test_list_reports_live_counts_from_qdrant(client):
    store = _FakeCollectionStore()
    _use(store, _FakeQdrant(chunk_count=7, docs=[{"id": "d1", "filename": "a.md"}]))

    created = (await client.post(BASE, json={"name": "Docs"})).json()
    listed = (await client.get(BASE)).json()

    assert listed[0]["id"] == created["id"]
    assert listed[0]["chunk_count"] == 7
    assert listed[0]["document_count"] == 1


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
    _use(store, _FakeQdrant(chunk_count=2, docs=docs))

    cid = (await client.post(BASE, json={"name": "Docs"})).json()["id"]
    resp = await client.get(f"{BASE}/{cid}/documents")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["filename"] == "a.md"
