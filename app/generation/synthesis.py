import json
from pathlib import Path

from jinja2 import Template

from app.models.schemas import Citation, DocumentChunk, RetrievedChunk

PROMPT_PATH = Path(__file__).parent / "prompts" / "rag_v1.md"


def render_rag_prompt(chunks: list[DocumentChunk], question: str) -> str:
    template = Template(PROMPT_PATH.read_text(encoding="utf-8"))
    return template.render(context=chunks, question=question)


def parse_answer(raw: str) -> tuple[str, list[int], str]:
    """Parse the LLM's JSON answer; fall back to raw text on any failure.

    Tolerant of code fences and of surrounding prose (e.g. a preamble or a
    trailing "Note: ..."), which smaller models often add around the JSON.
    """
    data = _extract_json_object(raw)
    if isinstance(data, dict):
        return (
            data.get("answer", ""),
            data.get("citations", []),
            data.get("confidence", "medium"),
        )
    return raw, [], "medium"


def _extract_json_object(raw: str) -> dict | None:
    text = raw
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the first balanced {...} object and parse that (ignores surrounding prose).
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


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
