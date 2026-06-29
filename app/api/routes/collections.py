from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import Principal, get_collection_store, get_principal, get_store
from app.db.collection_store import CollectionStore
from app.db.qdrant_store import QdrantStore
from app.models.schemas import Collection, CollectionCreate, Document

router = APIRouter()


def _with_counts(record: dict, store: QdrantStore, tenant_id: str) -> Collection:
    filters = {"collection_id": record["id"], "tenant_id": tenant_id}
    chunk_count = store.count_points(filters)
    document_count = len(store.list_documents(filters)) if chunk_count else 0
    return Collection(**record, chunk_count=chunk_count, document_count=document_count)


@router.get("/collections", response_model=list[Collection])
async def list_collections(
    collections: CollectionStore = Depends(get_collection_store),
    store: QdrantStore = Depends(get_store),
    principal: Principal = Depends(get_principal),
) -> list[Collection]:
    tenant = principal.tenant_id
    return [_with_counts(r, store, tenant) for r in collections.list(tenant)]


@router.post("/collections", response_model=Collection)
async def create_collection(
    body: CollectionCreate,
    collections: CollectionStore = Depends(get_collection_store),
    principal: Principal = Depends(get_principal),
) -> Collection:
    record = {
        "id": uuid4().hex,
        "name": body.name,
        "description": body.description,
        "tags": body.tags,
        "status": "ready",
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "tenant_id": principal.tenant_id,
    }
    collections.create(record["id"], record)
    return Collection(**record, chunk_count=0, document_count=0)


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: str,
    collections: CollectionStore = Depends(get_collection_store),
    principal: Principal = Depends(get_principal),
) -> dict:
    if not collections.delete(collection_id, principal.tenant_id):
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"status": "deleted", "id": collection_id}


@router.get("/collections/{collection_id}/documents", response_model=list[Document])
async def list_collection_documents(
    collection_id: str,
    collections: CollectionStore = Depends(get_collection_store),
    store: QdrantStore = Depends(get_store),
    principal: Principal = Depends(get_principal),
) -> list[Document]:
    if collections.get(collection_id, principal.tenant_id) is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    docs = store.list_documents({"collection_id": collection_id, "tenant_id": principal.tenant_id})
    return [Document(**doc) for doc in docs]
