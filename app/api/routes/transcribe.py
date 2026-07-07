"""Voice queries: turn an uploaded audio clip into text the client can send to
/query. Runs the local whisper model — no cloud STT service involved."""

import asyncio
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.api.dependencies import enforce_rate_limit, get_principal
from app.core.config import settings
from app.models.schemas import TranscribeResponse

router = APIRouter()


async def get_transcriber(request: Request):
    if not hasattr(request.app.state, "transcriber"):
        from app.ingestion.transcriber import get_transcriber as load

        request.app.state.transcriber = load()
    return request.app.state.transcriber


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    dependencies=[Depends(get_principal), Depends(enforce_rate_limit)],
)
async def transcribe_audio(
    file: UploadFile = File(...),
    transcriber=Depends(get_transcriber),
) -> TranscribeResponse:
    contents = await file.read()
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Audio exceeds the {settings.max_upload_bytes} byte limit",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    suffix = Path(file.filename or "clip.webm").suffix or ".webm"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        # CPU-bound; keep it off the event loop.
        text = await asyncio.to_thread(transcriber.transcribe, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return TranscribeResponse(text=text)
