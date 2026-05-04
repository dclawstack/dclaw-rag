from pathlib import Path

from app.ingestion.extractors.base import Extractor


class MarkdownExtractor(Extractor):
    supported_extensions = (".md", ".markdown", ".txt")

    def extract(self, file_path: Path) -> str:
        return file_path.read_text(encoding="utf-8")
