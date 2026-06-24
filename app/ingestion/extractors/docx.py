from pathlib import Path

from app.ingestion.extractors.base import Extractor


class DocxExtractor(Extractor):
    supported_extensions = (".docx",)

    def extract(self, file_path: Path) -> str:
        # Lazy import so the registry can load without python-docx present.
        import docx

        document = docx.Document(str(file_path))
        return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())
