from app.api.dependencies import get_collection_store, get_store
from app.api.main import app


class _FakeCollectionStore:
    def list(self, tenant_id):
        return [{"id": "a"}, {"id": "b"}]


class _FakeQdrant:
    def count_documents(self, filters=None):
        return 3

    def count_points(self, filters=None):
        return 9


async def test_stats_counts(client):
    app.dependency_overrides[get_collection_store] = lambda: _FakeCollectionStore()
    app.dependency_overrides[get_store] = lambda: _FakeQdrant()

    resp = await client.get("/api/v1/rag/stats")

    assert resp.status_code == 200
    assert resp.json() == {"collections": 2, "documents": 3, "chunks": 9}
