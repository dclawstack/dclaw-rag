from pathlib import Path

from app.ingestion.extractors.base import Extractor


class AudioExtractor(Extractor):
    """Audio -> transcript, so recordings ingest like any other document."""

    supported_extensions = (".mp3", ".wav", ".m4a", ".ogg", ".flac")

    def extract(self, file_path: Path) -> str:
        from app.ingestion.transcriber import get_transcriber

        return get_transcriber().transcribe(file_path)
