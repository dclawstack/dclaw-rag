from fastapi import Depends, Header, HTTPException, Request

from app.db.api_key_store import ApiKeyStore
from app.db.collection_store import CollectionStore
from app.db.document_store import DocumentStore
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


async def get_collection_store(request: Request) -> CollectionStore:
    if not hasattr(request.app.state, "collection_store"):
        request.app.state.collection_store = CollectionStore()
    return request.app.state.collection_store


async def get_api_key_store(request: Request) -> ApiKeyStore:
    if not hasattr(request.app.state, "api_key_store"):
        request.app.state.api_key_store = ApiKeyStore()
    return request.app.state.api_key_store


async def get_document_store(request: Request) -> DocumentStore:
    if not hasattr(request.app.state, "document_store"):
        request.app.state.document_store = DocumentStore()
    return request.app.state.document_store


class Principal:
    """The authenticated caller, resolved from an API key."""

    def __init__(self, tenant_id: str, key_name: str = "") -> None:
        self.tenant_id = tenant_id
        self.key_name = key_name


async def get_principal(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    store: ApiKeyStore = Depends(get_api_key_store),
) -> Principal:
    raw_key = None
    if authorization and authorization.lower().startswith("bearer "):
        raw_key = authorization[7:].strip()
    elif x_api_key:
        raw_key = x_api_key.strip()
    if not raw_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    record = store.get(raw_key)
    if not record:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return Principal(tenant_id=record["tenant_id"], key_name=record.get("name", ""))
