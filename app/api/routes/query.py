import time

from fastapi import APIRouter, Depends

from app.api.dependencies import get_llm, get_searcher
from app.generation.llm_gateway import LLMGateway
from app.generation.synthesis import (
    build_citations,
    parse_answer,
    render_rag_prompt,
    to_retrieved_chunk,
)
from app.models.schemas import QueryRequest, QueryResponse
from app.retrieval.search import Searcher

router = APIRouter()


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

    prompt = render_rag_prompt(chunks, request.question)
    messages = [
        {"role": "system", "content": "You are a helpful RAG assistant."},
        {"role": "user", "content": prompt},
    ]

    raw = await llm.complete(messages, temperature=0.2)
    answer, citation_indices, confidence = parse_answer(raw)

    retrieved = [to_retrieved_chunk(c) for c in chunks]

    return QueryResponse(
        query=request.question,
        answer=answer,
        results=retrieved,
        retrieved_chunks=retrieved,
        citations=build_citations(citation_indices, chunks),
        confidence=confidence,
        latency_ms=_elapsed_ms(start),
    )


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)
