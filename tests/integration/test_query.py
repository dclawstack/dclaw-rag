from datetime import UTC, datetime
from uuid import uuid4

from app.api.dependencies import get_llm, get_searcher
from app.api.main import app
from app.models.schemas import ChunkMetadata, DocumentChunk

QUERY_PATH = "/api/v1/rag/query"


def _fake_chunk(text: str = "Q3 revenue was $5M.", title: str = "Report") -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        text=text,
        score=0.9,
        metadata=ChunkMetadata(
            doc_id=uuid4(),
            chunk_index=0,
            source="report.md",
            title=title,
            created_at=datetime.now(tz=UTC),
        ),
    )


class _FakeSearcher:
    def __init__(self, chunks):
        self._chunks = chunks

    def search(self, query, top_k=10, filters=None):
        return self._chunks


class _FakeLLM:
    async def complete(self, messages, temperature=0.2):
        return '{"answer": "Q3 revenue was $5M.", "citations": [1], "confidence": "high"}'


async def test_query_returns_full_contract(client):
    chunk = _fake_chunk()
    app.dependency_overrides[get_searcher] = lambda: _FakeSearcher([chunk])
    app.dependency_overrides[get_llm] = lambda: _FakeLLM()

    resp = await client.post(QUERY_PATH, json={"question": "What was Q3 revenue?", "top_k": 5})

    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "query",
        "answer",
        "results",
        "retrieved_chunks",
        "citations",
        "confidence",
        "latency_ms",
    ):
        assert key in body, f"missing key: {key}"

    assert body["answer"] == "Q3 revenue was $5M."
    assert body["confidence"] == "high"
    assert isinstance(body["latency_ms"], (int, float))

    rc = body["retrieved_chunks"][0]
    assert rc["chunk_id"] == str(chunk.id)
    assert rc["document_name"] == "Report"
    assert rc["score"] == 0.9

    citation = body["citations"][0]
    assert citation["index"] == 1
    assert citation["chunk_id"] == str(chunk.id)
    assert citation["source"] == "report.md"


async def test_query_with_no_results_is_low_confidence(client):
    app.dependency_overrides[get_searcher] = lambda: _FakeSearcher([])
    app.dependency_overrides[get_llm] = lambda: _FakeLLM()

    resp = await client.post(QUERY_PATH, json={"question": "nothing"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] == "low"
    assert body["retrieved_chunks"] == []
    assert body["citations"] == []
