import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends
from jinja2 import Template

from app.api.dependencies import get_llm, get_searcher
from app.generation.llm_gateway import LLMGateway
from app.models.schemas import (
    Citation,
    DocumentChunk,
    QueryRequest,
    QueryResponse,
    RetrievedChunk,
)
from app.retrieval.search import Searcher

router = APIRouter()

PROMPT_PATH = Path(__file__).parents[2] / "generation" / "prompts" / "rag_v1.md"


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    searcher: Searcher = Depends(get_searcher),
    llm: LLMGateway = Depends(get_llm),
) -> QueryResponse:
    start = time.perf_counter()

    filters = request.filters.copy()
    if request.tenant_id:
        filters["tenant_id"] = request.tenant_id
    if request.collection_id:
        filters["collection_id"] = request.collection_id

    chunks = searcher.search(request.question, top_k=request.top_k, filters=filters or None)

    if not chunks:
        return QueryResponse(
            query=request.question,
            answer="I don't have enough information to answer that.",
            results=[],
            retrieved_chunks=[],
            citations=[],
            confidence="low",
            latency_ms=_elapsed_ms(start),
        )

    prompt_template = Template(PROMPT_PATH.read_text(encoding="utf-8"))
    prompt = prompt_template.render(context=chunks, question=request.question)

    messages = [
        {"role": "system", "content": "You are a helpful RAG assistant."},
        {"role": "user", "content": prompt},
    ]

    raw = await llm.complete(messages, temperature=0.2)
    answer, citations, confidence = _parse_output(raw)

    retrieved = [_to_retrieved(c) for c in chunks]
    citation_objs = [
        Citation(
            index=ci,
            chunk_id=str(chunks[ci - 1].id),
            text=chunks[ci - 1].text,
            source=chunks[ci - 1].metadata.source,
        )
        for ci in citations
        if 1 <= ci <= len(chunks)
    ]

    return QueryResponse(
        query=request.question,
        answer=answer,
        results=retrieved,
        retrieved_chunks=retrieved,
        citations=citation_objs,
        confidence=confidence,
        latency_ms=_elapsed_ms(start),
    )


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _to_retrieved(chunk: DocumentChunk) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk.id,
        chunk_id=str(chunk.id),
        text=chunk.text,
        score=float(chunk.score or 0.0),
        document_name=chunk.metadata.title or chunk.metadata.source,
        metadata=chunk.metadata,
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
