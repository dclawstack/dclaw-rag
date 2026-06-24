import json
from pathlib import Path

from jinja2 import Template

from app.models.schemas import Citation, DocumentChunk, RetrievedChunk

PROMPT_PATH = Path(__file__).parent / "prompts" / "rag_v1.md"


def render_rag_prompt(chunks: list[DocumentChunk], question: str) -> str:
    template = Template(PROMPT_PATH.read_text(encoding="utf-8"))
    return template.render(context=chunks, question=question)


def parse_answer(raw: str) -> tuple[str, list[int], str]:
    """Parse the LLM's JSON answer; fall back to raw text on any failure."""
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        data = json.loads(raw.strip())
        return (
            data.get("answer", ""),
            data.get("citations", []),
            data.get("confidence", "medium"),
        )
    except Exception:
        return raw, [], "medium"


def to_retrieved_chunk(chunk: DocumentChunk) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk.id,
        chunk_id=str(chunk.id),
        text=chunk.text,
        score=float(chunk.score or 0.0),
        document_name=chunk.metadata.title or chunk.metadata.source,
        metadata=chunk.metadata,
    )


def build_citations(indices: list[int], chunks: list[DocumentChunk]) -> list[Citation]:
    return [
        Citation(
            index=ci,
            chunk_id=str(chunks[ci - 1].id),
            text=chunks[ci - 1].text,
            source=chunks[ci - 1].metadata.source,
        )
        for ci in indices
        if 1 <= ci <= len(chunks)
    ]
