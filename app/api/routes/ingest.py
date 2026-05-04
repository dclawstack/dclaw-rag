from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.dependencies import get_pipeline
from app.core.exceptions import IngestionError
from app.ingestion.pipeline import IngestionPipeline
from app.models.schemas import IngestRequest, IngestResponse

router = APIRouter()


@router.post("/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    source: str = Form(...),
    title: str | None = Form(None),
    tags: str = Form(""),
    tenant_id: str | None = Form(None),
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
        request = IngestRequest(
            source=source,
            title=title or file.filename,
            tags=[t.strip() for t in tags.split(",") if t.strip()],
            tenant_id=tenant_id,
        )
        doc_id = pipeline.ingest_file(tmp_path, request)
    finally:
        tmp_path.unlink(missing_ok=True)

    return IngestResponse(doc_id=doc_id, chunks_inserted=0, status="success")


@router.post("/text", response_model=IngestResponse)
async def ingest_text(
    text: str,
    request: IngestRequest,
    pipeline: IngestionPipeline = Depends(get_pipeline),
) -> IngestResponse:
    doc_id = pipeline.ingest_text(text, request)
    return IngestResponse(doc_id=doc_id, chunks_inserted=0, status="success")
