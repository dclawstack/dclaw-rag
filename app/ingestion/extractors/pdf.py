from pathlib import Path

from pypdf import PdfReader

from app.ingestion.extractors.base import Extractor


class PDFExtractor(Extractor):
    supported_extensions = (".pdf",)

    def extract(self, file_path: Path) -> str:
        reader = PdfReader(str(file_path))
        parts: list[str] = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n\n".join(parts)
