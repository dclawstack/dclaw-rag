from fastapi import APIRouter, Depends

from app.api.dependencies import get_collection_store, get_store
from app.db.collection_store import CollectionStore
from app.db.qdrant_store import QdrantStore
from app.models.schemas import Stats

router = APIRouter()


@router.get("/stats", response_model=Stats)
async def stats(
    collections: CollectionStore = Depends(get_collection_store),
    store: QdrantStore = Depends(get_store),
) -> Stats:
    return Stats(
        collections=len(collections.list()),
        documents=len(store.list_documents()),
        chunks=store.count_points(),
    )
