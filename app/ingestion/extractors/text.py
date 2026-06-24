from pathlib import Path

from app.ingestion.extractors.base import Extractor


class PlainTextExtractor(Extractor):
    """Generic reader for plain-text formats not covered by a richer extractor."""

    supported_extensions = (".text", ".log", ".rst", ".json", ".yaml", ".yml")

    def extract(self, file_path: Path) -> str:
        return file_path.read_text(encoding="utf-8", errors="ignore")
