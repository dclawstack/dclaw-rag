from pathlib import Path

from app.ingestion.extractors.base import Extractor


class RTFExtractor(Extractor):
    supported_extensions = (".rtf",)

    def extract(self, file_path: Path) -> str:
        from striprtf.striprtf import rtf_to_text

        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        return rtf_to_text(raw).strip()
