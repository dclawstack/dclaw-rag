from datetime import UTC, datetime
from uuid import UUID

from app.api.dependencies import get_llm, get_searcher
from app.api.main import app
from app.models.schemas import ChunkMetadata, DocumentChunk

PATH = "/api/v1/rag/agent"


def _chunk() -> DocumentChunk:
    return DocumentChunk(
        id=UUID(int=1),
        text="context",
        score=0.7,
        metadata=ChunkMetadata(
            doc_id=UUID(int=0),
            chunk_index=0,
            source="r.md",
            title="R",
            created_at=datetime.now(tz=UTC),
        ),
    )


class _ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def complete(self, messages, temperature=0.2):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


class _Searcher:
    def search(self, query, top_k=10, filters=None):
        return [_chunk()]


async def test_agent_endpoint_returns_full_contract(client):
    app.dependency_overrides[get_searcher] = lambda: _Searcher()
    app.dependency_overrides[get_llm] = lambda: _ScriptedLLM(
        ['["a", "b"]', '{"answer":"Done.","citations":[1],"confidence":"high"}']
    )

    resp = await client.post(PATH, json={"question": "explain", "max_steps": 3, "top_k": 2})

    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "query",
        "answer",
        "citations",
        "retrieved_chunks",
        "confidence",
        "steps",
        "latency_ms",
    ):
        assert key in body, f"missing key: {key}"

    assert body["answer"] == "Done."
    assert body["confidence"] == "high"
    assert [s["sub_question"] for s in body["steps"]] == ["a", "b"]
    assert body["steps"][0]["n_results"] == 1
    assert body["citations"][0]["index"] == 1
