import time

from fastapi import APIRouter, Depends

from app.api.dependencies import get_llm, get_searcher
from app.generation.agent import AgenticRAG
from app.generation.llm_gateway import LLMGateway
from app.models.schemas import AgentRequest, AgentResponse
from app.retrieval.search import Searcher

router = APIRouter()


@router.post("/agent", response_model=AgentResponse)
async def agent_query(
    request: AgentRequest,
    searcher: Searcher = Depends(get_searcher),
    llm: LLMGateway = Depends(get_llm),
) -> AgentResponse:
    start = time.perf_counter()

    filters = request.filters.copy()
    if request.tenant_id:
        filters["tenant_id"] = request.tenant_id
    if request.collection_id:
        filters["collection_id"] = request.collection_id

    agent = AgenticRAG(searcher=searcher, llm=llm)
    result = await agent.run(
        request.question,
        top_k=request.top_k,
        filters=filters or None,
        max_steps=request.max_steps,
    )

    return AgentResponse(
        query=request.question,
        answer=result.answer,
        citations=result.citations,
        retrieved_chunks=result.retrieved_chunks,
        confidence=result.confidence,
        steps=result.steps,
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
    )
