from datetime import UTC, datetime
from uuid import uuid4

from app.api.dependencies import get_llm, get_searcher
from app.api.main import app
from app.models.schemas import ChunkMetadata, DocumentChunk

QUERY_PATH = "/api/v1/rag/query"
ANSWER = '{"answer": "Q3 revenue was $5M.", "citations": [1], "confidence": "high"}'


def _chunk(score: float) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        text="Q3 revenue was $5M.",
        score=score,
        metadata=ChunkMetadata(
            doc_id=uuid4(),
            chunk_index=0,
            source="report.md",
            title="Report",
            created_at=datetime.now(tz=UTC),
        ),
    )


class _Searcher:
    def __init__(self, chunks):
        self._chunks = chunks

    def search(self, query, top_k=10, filters=None):
        return self._chunks


class _ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def complete(self, messages, temperature=0.2):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


class _ExplodingLLM:
    def __init__(self):
        self.called = False

    async def complete(self, messages, temperature=0.2):
        self.called = True
        raise AssertionError("LLM must not be called when abstaining")


async def test_abstains_when_top_score_below_threshold(client):
    llm = _ExplodingLLM()
    app.dependency_overrides[get_searcher] = lambda: _Searcher([_chunk(-1.0)])
    app.dependency_overrides[get_llm] = lambda: llm

    resp = await client.post(QUERY_PATH, json={"question": "off topic?", "top_k": 5})

    assert resp.status_code == 200
    body = resp.json()
    assert body["abstained"] is True
    assert body["confidence"] == "low"
    assert body["citations"] == []
    assert "enough" in body["answer"].lower()
    assert llm.called is False  # no generation on abstention


async def test_grounded_answer_is_verified(client):
    app.dependency_overrides[get_searcher] = lambda: _Searcher([_chunk(5.0)])
    app.dependency_overrides[get_llm] = lambda: _ScriptedLLM(
        [ANSWER, '{"faithfulness": "grounded", "unsupported_claims": []}']
    )

    resp = await client.post(QUERY_PATH, json={"question": "What was Q3 revenue?", "top_k": 5})

    body = resp.json()
    assert body["abstained"] is False
    assert body["faithfulness"] == "grounded"
    assert body["unsupported_claims"] == []
    assert body["answer"] == "Q3 revenue was $5M."


async def test_partial_faithfulness_lists_unsupported_claims(client):
    app.dependency_overrides[get_searcher] = lambda: _Searcher([_chunk(5.0)])
    app.dependency_overrides[get_llm] = lambda: _ScriptedLLM(
        [ANSWER, '{"faithfulness": "partial", "unsupported_claims": ["The CEO resigned."]}']
    )

    resp = await client.post(QUERY_PATH, json={"question": "x", "top_k": 5})

    body = resp.json()
    assert body["faithfulness"] == "partial"
    assert body["unsupported_claims"] == ["The CEO resigned."]


async def test_verify_false_skips_the_verification_call(client):
    llm = _ScriptedLLM([ANSWER])
    app.dependency_overrides[get_searcher] = lambda: _Searcher([_chunk(5.0)])
    app.dependency_overrides[get_llm] = lambda: llm

    resp = await client.post(QUERY_PATH, json={"question": "x", "top_k": 5, "verify": False})

    body = resp.json()
    assert body["faithfulness"] is None
    assert llm.calls == 1  # answer only — no second (verification) call
