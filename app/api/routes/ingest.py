import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.dependencies import (
    Principal,
    enforce_rate_limit,
    get_document_store,
    get_principal,
)
from app.core import metrics
from app.core.config import settings
from app.core.exceptions import IngestionError
from app.db.document_store import DocumentStore
from app.ingestion.pipeline import checksum, extract_file_text
from app.ingestion.tasks import dispatch_ingestion
from app.models.schemas import Document, IngestRequest, IngestResponse, TextIngestRequest

router = APIRouter()


def _parse_metadata(raw: str) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_request(
    metadata: dict, tenant_id: str, default_title: str | None = None
) -> IngestRequest:
    # tenant is forced from the principal; a client-supplied tenant_id is ignored.
    return IngestRequest(
        source=metadata.get("source") or "user-upload",
        title=metadata.get("title") or default_title,
        tags=metadata.get("tags") or [],
        tenant_id=tenant_id,
        collection_id=metadata.get("collection_id"),
    )


def _enqueue(text: str, request: IngestRequest, store: DocumentStore) -> IngestResponse:
    """Register the document (pending) and hand the heavy work to the worker.

    Idempotent by content checksum: a still-pending/ready document with the same
    content is returned as-is; a previously failed one is retried under its id."""
    if not text.strip():
        raise IngestionError("No text to ingest")

    content_hash = checksum(text)
    existing = store.find_by_checksum(request.tenant_id or "", content_hash)
    if existing and existing["status"] != "failed":
        return IngestResponse(
            doc_id=UUID(existing["id"]),
            chunks_inserted=existing.get("chunk_count", 0),
            status=existing["status"],
        )

    doc_id = UUID(existing["id"]) if existing else uuid4()
    store.create(
        {
            "id": str(doc_id),
            "tenant_id": request.tenant_id,
            "collection_id": request.collection_id,
            "source": request.source,
            "title": request.title,
            "filename": request.title or request.source or str(doc_id),
            "status": "pending",
            "checksum": content_hash,
            "chunk_count": 0,
            "error": None,
            "created_at": datetime.now(tz=UTC).isoformat(),
        }
    )
    dispatch_ingestion(str(doc_id), text, request.model_dump(mode="json"))
    metrics.INGEST_ENQUEUED.inc()
    return IngestResponse(doc_id=doc_id, chunks_inserted=0, status="pending")


@router.post(
    "/upload", response_model=IngestResponse, dependencies=[Depends(enforce_rate_limit)]
)
async def upload_document(
    file: UploadFile = File(...),
    metadata: str = Form("{}"),
    store: DocumentStore = Depends(get_document_store),
    principal: Principal = Depends(get_principal),
) -> IngestResponse:
    if not file.filename:
        raise IngestionError("No filename provided")

    suffix = Path(file.filename).suffix
    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_bytes} byte limit",
        )

    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        text = extract_file_text(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    request = _build_request(
        _parse_metadata(metadata), principal.tenant_id, default_title=file.filename
    )
    return _enqueue(text, request, store)


@router.post(
    "/text", response_model=IngestResponse, dependencies=[Depends(enforce_rate_limit)]
)
async def ingest_text(
    body: TextIngestRequest,
    store: DocumentStore = Depends(get_document_store),
    principal: Principal = Depends(get_principal),
) -> IngestResponse:
    request = _build_request(body.metadata, principal.tenant_id, default_title="Text ingestion")
    return _enqueue(body.text, request, store)


@router.get("/{doc_id}", response_model=Document)
async def get_document(
    doc_id: str,
    store: DocumentStore = Depends(get_document_store),
    principal: Principal = Depends(get_principal),
) -> Document:
    record = store.get(doc_id, principal.tenant_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return Document(**record)
