from app.api.dependencies import get_llm, get_query_cache, get_searcher
from app.api.main import app

CACHED = {
    "query": "hi",
    "answer": "cached answer",
    "results": [],
    "retrieved_chunks": [],
    "citations": [],
    "confidence": "high",
    "abstained": False,
    "latency_ms": 0.0,
}


class _HitCache:
    def get(self, tenant_id, params):
        return CACHED

    def set(self, tenant_id, params, value):
        pass


class _ExplodingSearcher:
    def search(self, *args, **kwargs):
        raise AssertionError("searcher must not be called on a cache hit")


async def test_cache_hit_short_circuits_retrieval_and_llm(client):
    app.dependency_overrides[get_query_cache] = lambda: _HitCache()
    app.dependency_overrides[get_searcher] = lambda: _ExplodingSearcher()
    app.dependency_overrides[get_llm] = lambda: object()

    resp = await client.post("/api/v1/rag/query", json={"question": "hi", "top_k": 5})

    assert resp.status_code == 200
    assert resp.json()["answer"] == "cached answer"  # served from cache
