from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_collection_store, get_store
from app.db.collection_store import CollectionStore
from app.db.qdrant_store import QdrantStore
from app.models.schemas import Collection, CollectionCreate, Document

router = APIRouter()


def _with_counts(record: dict, store: QdrantStore) -> Collection:
    filters = {"collection_id": record["id"]}
    chunk_count = store.count_points(filters)
    document_count = len(store.list_documents(filters)) if chunk_count else 0
    return Collection(**record, chunk_count=chunk_count, document_count=document_count)


@router.get("/collections", response_model=list[Collection])
async def list_collections(
    collections: CollectionStore = Depends(get_collection_store),
    store: QdrantStore = Depends(get_store),
) -> list[Collection]:
    return [_with_counts(record, store) for record in collections.list()]


@router.post("/collections", response_model=Collection)
async def create_collection(
    body: CollectionCreate,
    collections: CollectionStore = Depends(get_collection_store),
) -> Collection:
    record = {
        "id": uuid4().hex,
        "name": body.name,
        "description": body.description,
        "tags": body.tags,
        "status": "ready",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    collections.create(record["id"], record)
    return Collection(**record, chunk_count=0, document_count=0)


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: str,
    collections: CollectionStore = Depends(get_collection_store),
) -> dict:
    if not collections.delete(collection_id):
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"status": "deleted", "id": collection_id}


@router.get("/collections/{collection_id}/documents", response_model=list[Document])
async def list_collection_documents(
    collection_id: str,
    collections: CollectionStore = Depends(get_collection_store),
    store: QdrantStore = Depends(get_store),
) -> list[Document]:
    if collections.get(collection_id) is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    docs = store.list_documents({"collection_id": collection_id})
    return [Document(**doc) for doc in docs]
