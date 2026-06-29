import time

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    Principal,
    enforce_rate_limit,
    get_llm,
    get_principal,
    get_searcher,
)
from app.core.config import settings
from app.generation.llm_gateway import LLMGateway
from app.generation.synthesis import (
    build_citations,
    parse_answer,
    render_rag_prompt,
    to_retrieved_chunk,
    verify_answer,
)
from app.models.schemas import QueryRequest, QueryResponse
from app.retrieval.search import Searcher

router = APIRouter()

ABSTAIN_MESSAGE = (
    "I don't have enough relevant information in the knowledge base to answer that "
    "confidently. Try rephrasing, or ingest a document that covers it."
)


@router.post(
    "/query", response_model=QueryResponse, dependencies=[Depends(enforce_rate_limit)]
)
async def query(
    request: QueryRequest,
    searcher: Searcher = Depends(get_searcher),
    llm: LLMGateway = Depends(get_llm),
    principal: Principal = Depends(get_principal),
) -> QueryResponse:
    start = time.perf_counter()

    # tenant comes from the authenticated principal, never the request body
    filters = request.filters.copy()
    filters["tenant_id"] = principal.tenant_id
    if request.collection_id:
        filters["collection_id"] = request.collection_id

    chunks = searcher.search(request.question, top_k=request.top_k, filters=filters or None)
    retrieved = [to_retrieved_chunk(c) for c in chunks]

    # Honest abstention: if nothing cleared the relevance bar, don't ask the LLM —
    # saying "I don't know" beats a confident hallucination from weak context.
    top_score = max((c.score or 0.0 for c in chunks), default=float("-inf"))
    if not chunks or top_score < settings.abstain_threshold:
        return QueryResponse(
            query=request.question,
            answer=ABSTAIN_MESSAGE,
            results=retrieved,
            retrieved_chunks=retrieved,
            citations=[],
            confidence="low",
            abstained=True,
            latency_ms=_elapsed_ms(start),
        )

    prompt = render_rag_prompt(chunks, request.question)
    messages = [
        {"role": "system", "content": "You are a helpful RAG assistant."},
        {"role": "user", "content": prompt},
    ]
    raw = await llm.complete(messages, temperature=0.2)
    answer, citation_indices, confidence = parse_answer(raw)

    faithfulness: str | None = None
    unsupported_claims: list[str] = []
    if settings.verify_answers and request.verify:
        faithfulness, unsupported_claims = await verify_answer(answer, chunks, llm)

    return QueryResponse(
        query=request.question,
        answer=answer,
        results=retrieved,
        retrieved_chunks=retrieved,
        citations=build_citations(citation_indices, chunks),
        confidence=confidence,
        abstained=False,
        faithfulness=faithfulness,
        unsupported_claims=unsupported_claims,
        latency_ms=_elapsed_ms(start),
    )


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)
