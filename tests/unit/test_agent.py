from uuid import UUID

from app.generation.agent import AgenticRAG
from app.models.schemas import ChunkMetadata, DocumentChunk


def _chunk(n: int) -> DocumentChunk:
    return DocumentChunk(
        id=UUID(int=n),
        text=f"c{n}",
        score=0.5,
        metadata=ChunkMetadata(doc_id=UUID(int=0), chunk_index=n, source="s", title="Doc"),
    )


class _ScriptedLLM:
    """Returns queued responses in order (plan first, then synthesis)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def complete(self, messages, temperature=0.2):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


class _MapSearcher:
    def __init__(self, mapping, default=None):
        self.mapping = mapping
        self.default = default or []
        self.queries = []

    def search(self, query, top_k=10, filters=None):
        self.queries.append(query)
        return self.mapping.get(query, self.default)


async def test_agent_plans_retrieves_dedups_and_synthesizes():
    llm = _ScriptedLLM(
        ['["sub one", "sub two"]', '{"answer":"Final.","citations":[1],"confidence":"high"}']
    )
    a, b, c = _chunk(1), _chunk(2), _chunk(3)
    searcher = _MapSearcher({"sub one": [a, b], "sub two": [b, c]})

    result = await AgenticRAG(searcher=searcher, llm=llm).run("big q", top_k=5, max_steps=4)

    assert searcher.queries == ["sub one", "sub two"]  # retrieved per sub-question
    assert [s.sub_question for s in result.steps] == ["sub one", "sub two"]
    assert result.steps[0].n_results == 2
    assert len(result.retrieved_chunks) == 3  # union deduped by id (b shared)
    assert result.answer == "Final."
    assert result.confidence == "high"
    assert result.citations[0].index == 1


async def test_agent_falls_back_to_original_question_on_bad_plan():
    llm = _ScriptedLLM(["not json", '{"answer":"A","citations":[],"confidence":"medium"}'])
    searcher = _MapSearcher({}, default=[_chunk(1)])

    result = await AgenticRAG(searcher=searcher, llm=llm).run("the original question")

    assert searcher.queries == ["the original question"]
    assert len(result.steps) == 1
    assert result.steps[0].sub_question == "the original question"


async def test_agent_returns_low_confidence_when_no_results():
    llm = _ScriptedLLM(['["q"]'])
    searcher = _MapSearcher({}, default=[])

    result = await AgenticRAG(searcher=searcher, llm=llm).run("q")

    assert result.confidence == "low"
    assert result.retrieved_chunks == []
    assert result.answer.startswith("I don't have enough")
    assert llm.calls == 1  # only the planning call; synthesis skipped
