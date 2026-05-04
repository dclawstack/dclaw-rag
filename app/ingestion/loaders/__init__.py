from pathlib import Path

from app.core.exceptions import IngestionError
from app.ingestion.extractors.base import Extractor
from app.ingestion.extractors.markdown import MarkdownExtractor
from app.ingestion.extractors.pdf import PDFExtractor

_EXTRACTORS: list[type[Extractor]] = [
    PDFExtractor,
    MarkdownExtractor,
]


def get_extractor(file_path: Path) -> Extractor:
    suffix = file_path.suffix.lower()
    for cls in _EXTRACTORS:
        if suffix in cls.supported_extensions:
            return cls()
    raise IngestionError(f"No extractor registered for extension: {suffix}")
