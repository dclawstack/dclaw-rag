"""Local speech-to-text via faster-whisper (CPU, int8).

Backs both audio-file ingestion and the /transcribe voice-query endpoint. The
model (~145MB for `base`) is loaded lazily on first use and shared process-wide
so idle deployments and text-only users never pay for it.
"""

import threading
from pathlib import Path

from app.core.config import settings


class Transcriber:
    def __init__(self) -> None:
        from faster_whisper import WhisperModel

        self.model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")

    def transcribe(self, file_path: Path | str) -> str:
        segments, _info = self.model.transcribe(str(file_path), vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments).strip()


_transcriber: Transcriber | None = None
_lock = threading.Lock()


def get_transcriber() -> Transcriber:
    global _transcriber
    with _lock:
        if _transcriber is None:
            _transcriber = Transcriber()
    return _transcriber
