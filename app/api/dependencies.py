from fastapi import Request

from app.db.qdrant_store import QdrantStore
from app.generation.llm_gateway import LLMGateway, get_llm_gateway
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.search import Searcher


async def get_searcher(request: Request) -> Searcher:
    if not hasattr(request.app.state, "searcher"):
        request.app.state.searcher = Searcher()
    return request.app.state.searcher


async def get_pipeline(request: Request) -> IngestionPipeline:
    if not hasattr(request.app.state, "pipeline"):
        request.app.state.pipeline = IngestionPipeline()
    return request.app.state.pipeline


async def get_llm(request: Request) -> LLMGateway:
    if not hasattr(request.app.state, "llm"):
        request.app.state.llm = get_llm_gateway()
    return request.app.state.llm


async def get_store(request: Request) -> QdrantStore:
    if not hasattr(request.app.state, "store"):
        request.app.state.store = QdrantStore()
    return request.app.state.store
