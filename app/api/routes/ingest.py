import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.dependencies import get_pipeline
from app.core.exceptions import IngestionError
from app.ingestion.pipeline import IngestionPipeline
from app.models.schemas import IngestRequest, IngestResponse, TextIngestRequest

router = APIRouter()


def _parse_metadata(raw: str) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _build_request(metadata: dict, default_title: str | None = None) -> IngestRequest:
    return IngestRequest(
        source=metadata.get("source") or "user-upload",
        title=metadata.get("title") or default_title,
        tags=metadata.get("tags") or [],
        tenant_id=metadata.get("tenant_id"),
        collection_id=metadata.get("collection_id"),
    )


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    file: UploadFile = File(...),
    metadata: str = Form("{}"),
    pipeline: IngestionPipeline = Depends(get_pipeline),
) -> IngestResponse:
    if not file.filename:
        raise IngestionError("No filename provided")

    suffix = Path(file.filename).suffix
    contents = await file.read()

    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        request = _build_request(_parse_metadata(metadata), default_title=file.filename)
        doc_id, chunks_inserted = pipeline.ingest_file(tmp_path, request)
    finally:
        tmp_path.unlink(missing_ok=True)

    return IngestResponse(doc_id=doc_id, chunks_inserted=chunks_inserted, status="success")


@router.post("/text", response_model=IngestResponse)
async def ingest_text(
    body: TextIngestRequest,
    pipeline: IngestionPipeline = Depends(get_pipeline),
) -> IngestResponse:
    request = _build_request(body.metadata, default_title="Text ingestion")
    doc_id, chunks_inserted = pipeline.ingest_text(body.text, request)
    return IngestResponse(doc_id=doc_id, chunks_inserted=chunks_inserted, status="success")
