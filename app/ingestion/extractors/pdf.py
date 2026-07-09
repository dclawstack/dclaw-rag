from pathlib import Path

from pypdf import PdfReader

from app.core.config import settings
from app.ingestion.extractors.base import Extractor
from app.ingestion.extractors.ocr import extract_pdf_tables, ocr_pdf_pages


class PDFExtractor(Extractor):
    supported_extensions = (".pdf",)

    def extract(self, file_path: Path) -> str:
        parts: list[str] = []

        text = self._extract_text(file_path)
        if text:
            parts.append(text)

        # Tables are lost by plain text extraction — pull them out separately
        # (best-effort; a no-op without the 'vision' extra).
        if settings.extract_tables:
            tables = extract_pdf_tables(file_path)
            if tables:
                parts.append(tables)

        # Little/no extractable text => a scanned/image-only PDF: OCR the pages.
        combined = "\n\n".join(parts)
        if settings.ocr_scanned_pdfs and len(combined.strip()) < settings.ocr_min_chars:
            ocr_text = ocr_pdf_pages(file_path)
            if ocr_text.strip():
                parts.append(ocr_text)

        return "\n\n".join(parts)

    @staticmethod
    def _extract_text(file_path: Path) -> str:
        reader = PdfReader(str(file_path))
        pages = [page.extract_text() for page in reader.pages]
        return "\n\n".join(text for text in pages if text)
