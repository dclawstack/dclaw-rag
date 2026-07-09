"""Cross-source contradiction flagging (best-effort LLM check)."""

from uuid import uuid4

from app.generation.contradiction import detect_contradictions
from app.models.schemas import ChunkMetadata, DocumentChunk


def _chunk(source: str, text: str = "t") -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        text=text,
        metadata=ChunkMetadata(doc_id=uuid4(), chunk_index=0, source=source),
    )


class _LLM:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls = 0

    async def complete(self, messages, temperature=0.2):
        self.calls += 1
        return self.reply


async def test_no_check_with_single_source():
    llm = _LLM('{"contradictions": ["should not appear"]}')
    # Two chunks but ONE source — not a cross-source contradiction.
    out = await detect_contradictions([_chunk("a.pdf"), _chunk("a.pdf")], llm)
    assert out == []
    assert llm.calls == 0  # never asked the LLM


async def test_no_check_with_single_chunk():
    llm = _LLM('{"contradictions": ["x"]}')
    assert await detect_contradictions([_chunk("a.pdf")], llm) == []
    assert llm.calls == 0


async def test_parses_contradictions_across_sources():
    llm = _LLM('{"contradictions": ["[1] says $5M but [2] says $8M"]}')
    out = await detect_contradictions([_chunk("a.pdf"), _chunk("b.pdf")], llm)
    assert out == ["[1] says $5M but [2] says $8M"]
    assert llm.calls == 1


async def test_empty_list_when_no_conflicts():
    llm = _LLM('{"contradictions": []}')
    assert await detect_contradictions([_chunk("a.pdf"), _chunk("b.pdf")], llm) == []


async def test_fails_open_on_llm_error():
    class _Boom:
        async def complete(self, messages, temperature=0.2):
            raise RuntimeError("down")

    out = await detect_contradictions([_chunk("a.pdf"), _chunk("b.pdf")], _Boom())
    assert out == []


async def test_tolerates_bare_json_array():
    llm = _LLM('["[1] vs [2] conflict"]')
    out = await detect_contradictions([_chunk("a.pdf"), _chunk("b.pdf")], llm)
    assert out == ["[1] vs [2] conflict"]
