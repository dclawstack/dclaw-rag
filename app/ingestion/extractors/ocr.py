"""Lazy OCR + table helpers for visual documents (the 'vision' extra).

Every heavy/native dependency here is imported lazily, so the base install and
the ordinary text-ingestion path never pay for them. When a dep (or the system
`tesseract` binary) is missing, OCR raises a clear IngestionError pointing at the
extra; table extraction degrades silently to "no tables" so a normal PDF still
ingests its text.
"""

from pathlib import Path

import structlog

from app.core.exceptions import IngestionError

logger = structlog.get_logger(__name__)

# Image formats we OCR.
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".gif")

_VISION_HINT = (
    "install the 'vision' extra (pip install -e '.[vision]') and the system "
    "'tesseract' binary"
)


def _image_to_text(pil_image) -> str:
    try:
        import pytesseract
    except ImportError as exc:
        raise IngestionError(f"OCR requires pytesseract — {_VISION_HINT}") from exc
    try:
        return pytesseract.image_to_string(pil_image).strip()
    except Exception as exc:  # tesseract binary missing / unreadable image
        raise IngestionError(f"OCR failed ({exc}) — {_VISION_HINT}") from exc


def ocr_image_file(file_path: Path) -> str:
    """OCR an image file to text (raises IngestionError if OCR isn't available)."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise IngestionError(f"Image OCR requires Pillow — {_VISION_HINT}") from exc
    with Image.open(str(file_path)) as image:
        return _image_to_text(image)


def extract_pdf_tables(file_path: Path) -> str:
    """PDF tables as pipe-delimited text (matches the xlsx extractor's shape).

    Returns "" when pdfplumber is unavailable or the PDF has no tables — table
    extraction is best-effort and never blocks a normal text PDF.
    """
    try:
        import pdfplumber
    except ImportError:
        return ""
    blocks: list[str] = []
    try:
        with pdfplumber.open(str(file_path)) as pdf:
            for page_no, page in enumerate(pdf.pages, 1):
                for table_no, table in enumerate(page.extract_tables() or [], 1):
                    rows = [
                        " | ".join((cell or "").strip() for cell in row)
                        for row in table
                        if any(cell and str(cell).strip() for cell in row)
                    ]
                    if rows:
                        blocks.append(f"[Table p{page_no}.{table_no}]\n" + "\n".join(rows))
    except Exception as exc:  # malformed PDF — don't fail the whole ingestion
        logger.warning("pdf_table_extraction_failed", error=str(exc))
        return ""
    return "\n\n".join(blocks)


def ocr_pdf_pages(file_path: Path, dpi: int = 200) -> str:
    """Rasterize each PDF page and OCR it — for scanned/image-only PDFs.

    Returns "" if pymupdf is unavailable; raises IngestionError only if pymupdf
    is present but OCR itself can't run (so a missing tesseract is surfaced).
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        return ""
    from io import BytesIO

    try:
        from PIL import Image
    except ImportError as exc:
        raise IngestionError(f"Scanned-PDF OCR requires Pillow — {_VISION_HINT}") from exc

    zoom = dpi / 72.0
    pages: list[str] = []
    with fitz.open(str(file_path)) as doc:
        for page in doc:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            with Image.open(BytesIO(pixmap.tobytes("png"))) as image:
                text = _image_to_text(image)
            if text:
                pages.append(text)
    return "\n\n".join(pages)
