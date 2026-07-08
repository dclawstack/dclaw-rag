"""Self-correcting retrieval: reformulate + re-search only when the first
result is weak, and only keep the retry when it's actually better."""

from uuid import uuid4

import pytest

from app.core.config import settings
from app.models.schemas import ChunkMetadata, DocumentChunk
from app.retrieval import self_correct


def _chunk(score: float) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        text="t",
        metadata=ChunkMetadata(doc_id=uuid4(), chunk_index=0, source="s"),
        score=score,
    )


class _FakeSearcher:
    """Returns preset results per query; records the queries it was asked."""

    def __init__(self, results: dict[str, list[DocumentChunk]]):
        self.results = results
        self.queries: list[str] = []

    def search(self, query, top_k=10, filters=None):
        self.queries.append(query)
        return self.results.get(query, [])


class _FakeLLM:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = 0

    async def complete(self, messages, temperature=0.2):
        self.calls += 1
        return self.reply


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setattr(settings, "self_correct_retrieval", True)
    monkeypatch.setattr(settings, "self_correct_threshold", 0.5)


async def test_strong_first_result_skips_reformulation():
    searcher = _FakeSearcher({"q": [_chunk(0.8)]})
    llm = _FakeLLM("better query")

    chunks, reformulated = await self_correct.search_self_correcting(
        searcher, llm, "q", top_k=5, filters=None
    )

    assert reformulated is None
    assert chunks[0].score == 0.8
    assert llm.calls == 0  # no LLM round-trip on the common case
    assert searcher.queries == ["q"]


async def test_weak_result_reformulates_and_keeps_better():
    searcher = _FakeSearcher({"q": [_chunk(0.2)], "sharper q": [_chunk(0.9)]})
    llm = _FakeLLM("sharper q")

    chunks, reformulated = await self_correct.search_self_correcting(
        searcher, llm, "q", top_k=5, filters=None
    )

    assert reformulated == "sharper q"
    assert chunks[0].score == 0.9
    assert searcher.queries == ["q", "sharper q"]


async def test_weak_result_retry_not_better_keeps_original():
    searcher = _FakeSearcher({"q": [_chunk(0.3)], "sharper q": [_chunk(0.1)]})
    llm = _FakeLLM("sharper q")

    chunks, reformulated = await self_correct.search_self_correcting(
        searcher, llm, "q", top_k=5, filters=None
    )

    assert reformulated is None
    assert chunks[0].score == 0.3  # kept the better original


async def test_disabled_returns_first_result(monkeypatch):
    monkeypatch.setattr(settings, "self_correct_retrieval", False)
    searcher = _FakeSearcher({"q": [_chunk(0.1)]})
    llm = _FakeLLM("x")

    chunks, reformulated = await self_correct.search_self_correcting(
        searcher, llm, "q", top_k=5, filters=None
    )

    assert reformulated is None
    assert llm.calls == 0


async def test_reformulation_echoing_original_is_ignored():
    searcher = _FakeSearcher({"q": [_chunk(0.2)]})
    llm = _FakeLLM("  Q  ")  # same query, different whitespace/case

    chunks, reformulated = await self_correct.search_self_correcting(
        searcher, llm, "q", top_k=5, filters=None
    )

    assert reformulated is None
    assert searcher.queries == ["q"]  # no pointless re-search


async def test_llm_failure_falls_back_to_original():
    class _Boom:
        async def complete(self, messages, temperature=0.2):
            raise RuntimeError("llm down")

    searcher = _FakeSearcher({"q": [_chunk(0.2)]})
    chunks, reformulated = await self_correct.search_self_correcting(
        searcher, _Boom(), "q", top_k=5, filters=None
    )

    assert reformulated is None
    assert chunks[0].score == 0.2
