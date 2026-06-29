from fastapi import APIRouter, Depends

from app.api.dependencies import (
    Principal,
    get_collection_store,
    get_document_store,
    get_principal,
    get_store,
)
from app.db.collection_store import CollectionStore
from app.db.document_store import DocumentStore
from app.db.qdrant_store import QdrantStore
from app.models.schemas import Stats

router = APIRouter()


@router.get("/stats", response_model=Stats)
async def stats(
    collections: CollectionStore = Depends(get_collection_store),
    store: QdrantStore = Depends(get_store),
    docs: DocumentStore = Depends(get_document_store),
    principal: Principal = Depends(get_principal),
) -> Stats:
    tenant = principal.tenant_id
    return Stats(
        collections=len(collections.list(tenant)),
        documents=docs.count(tenant),
        chunks=store.count_points({"tenant_id": tenant}),
    )
