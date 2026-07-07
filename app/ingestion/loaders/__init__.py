from pathlib import Path

from app.core.exceptions import IngestionError
from app.ingestion.extractors.audio import AudioExtractor
from app.ingestion.extractors.base import Extractor
from app.ingestion.extractors.csv import CSVExtractor
from app.ingestion.extractors.docx import DocxExtractor
from app.ingestion.extractors.email import EmailExtractor
from app.ingestion.extractors.epub import EpubExtractor
from app.ingestion.extractors.html import HTMLExtractor
from app.ingestion.extractors.markdown import MarkdownExtractor
from app.ingestion.extractors.pdf import PDFExtractor
from app.ingestion.extractors.pptx import PptxExtractor
from app.ingestion.extractors.rtf import RTFExtractor
from app.ingestion.extractors.text import PlainTextExtractor
from app.ingestion.extractors.xlsx import XlsxExtractor

_EXTRACTORS: list[type[Extractor]] = [
    PDFExtractor,
    MarkdownExtractor,
    HTMLExtractor,
    CSVExtractor,
    DocxExtractor,
    PptxExtractor,
    XlsxExtractor,
    EpubExtractor,
    EmailExtractor,
    RTFExtractor,
    AudioExtractor,
    PlainTextExtractor,
]

_SNIFF_BYTES = 8192


def _sniffs_as_text(file_path: Path) -> bool:
    """True when the file's head is NUL-free valid UTF-8 (i.e. plain text)."""
    try:
        with file_path.open("rb") as handle:
            head = handle.read(_SNIFF_BYTES)
    except OSError:
        return False
    if not head or b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as exc:
        # A decode error at the very end is just a multi-byte char cut by the
        # sniff window; anywhere else means genuinely non-text content.
        return exc.start >= len(head) - 3
    return True


def get_extractor(file_path: Path) -> Extractor:
    suffix = file_path.suffix.lower()
    for cls in _EXTRACTORS:
        if suffix in cls.supported_extensions:
            return cls()
    # Unknown extension: accept anything that is actually plain text (source
    # code, configs, .tex, extension-less files, ...); reject binaries.
    if _sniffs_as_text(file_path):
        return PlainTextExtractor()
    raise IngestionError(f"Unsupported (non-text) file type: {suffix or file_path.name}")
