import json
from pathlib import Path

from fastapi import APIRouter, Depends
from jinja2 import Template

from app.api.dependencies import get_llm, get_searcher
from app.generation.llm_gateway import LLMGateway
from app.models.schemas import (
    Citation,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
)
from app.retrieval.search import Searcher

router = APIRouter()

PROMPT_PATH = Path(__file__).parents[2] / "generation" / "prompts" / "rag_v1.md"


@router.post("", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    searcher: Searcher = Depends(get_searcher),
    llm: LLMGateway = Depends(get_llm),
) -> QueryResponse:
    filters = request.filters.copy()
    if request.tenant_id:
        filters["tenant_id"] = request.tenant_id

    chunks = searcher.search(request.question, top_k=request.top_k, filters=filters or None)

    if not chunks:
        return QueryResponse(
            answer="I don't have enough information to answer that.",
            citations=[],
            confidence="low",
            retrieved_chunks=[],
        )

    prompt_template = Template(PROMPT_PATH.read_text(encoding="utf-8"))
    prompt = prompt_template.render(context=chunks, question=request.question)

    messages = [
        {"role": "system", "content": "You are a helpful RAG assistant."},
        {"role": "user", "content": prompt},
    ]

    raw = await llm.complete(messages, temperature=0.2)

    answer, citations, confidence = _parse_output(raw)

    citation_objs = [
        Citation(
            index=ci,
            chunk_id=chunks[ci - 1].id if ci <= len(chunks) else chunks[0].id,
            source=chunks[ci - 1].metadata.source if ci <= len(chunks) else "",
        )
        for ci in citations
        if ci <= len(chunks)
    ]

    return QueryResponse(
        answer=answer,
        citations=citation_objs,
        confidence=confidence,
        retrieved_chunks=[
            RetrievedChunk(
                id=c.id,
                text=c.text,
                score=getattr(c, "score", 0.0),
                metadata=c.metadata,
            )
            for c in chunks
        ],
    )


def _parse_output(raw: str) -> tuple[str, list[int], str]:
    try:
        # Extract JSON if wrapped in markdown
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
