from fastapi import APIRouter, Depends

from app.api.dependencies import Principal, get_collection_store, get_principal, get_store
from app.db.collection_store import CollectionStore
from app.db.qdrant_store import QdrantStore
from app.models.schemas import Stats

router = APIRouter()


@router.get("/stats", response_model=Stats)
async def stats(
    collections: CollectionStore = Depends(get_collection_store),
    store: QdrantStore = Depends(get_store),
    principal: Principal = Depends(get_principal),
) -> Stats:
    tenant_filter = {"tenant_id": principal.tenant_id}
    return Stats(
        collections=len(collections.list(principal.tenant_id)),
        documents=store.count_documents(tenant_filter),
        chunks=store.count_points(tenant_filter),
    )
