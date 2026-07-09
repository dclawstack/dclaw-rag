"""Visual-document ingestion: image routing, PDF table extraction, and
scanned-PDF OCR — all with the heavy 'vision' deps stubbed so this runs in CI."""

import builtins
from pathlib import Path

import pytest

from app.core.config import settings
from app.core.exceptions import IngestionError
from app.ingestion.extractors import ocr as ocr_mod
from app.ingestion.extractors import pdf as pdf_mod
from app.ingestion.extractors.image import ImageExtractor
from app.ingestion.extractors.pdf import PDFExtractor
from app.ingestion.loaders import get_extractor


def test_image_extensions_route_to_image_extractor():
    for ext in (".png", ".jpg", ".jpeg", ".tiff", ".webp", ".bmp"):
        assert isinstance(get_extractor(Path(f"scan{ext}")), ImageExtractor)


def test_pdf_appends_extracted_tables(monkeypatch):
    monkeypatch.setattr(settings, "extract_tables", True)
    monkeypatch.setattr(settings, "ocr_scanned_pdfs", False)
    monkeypatch.setattr(
        PDFExtractor, "_extract_text", staticmethod(lambda p: "Prose body. " * 20)
    )
    monkeypatch.setattr(pdf_mod, "extract_pdf_tables", lambda p: "[Table p1.1]\nRev | 5M")

    out = PDFExtractor().extract(Path("x.pdf"))

    assert "Prose body." in out
    assert "[Table p1.1]" in out and "Rev | 5M" in out


def test_pdf_ocr_runs_when_text_is_sparse(monkeypatch):
    monkeypatch.setattr(settings, "extract_tables", False)
    monkeypatch.setattr(settings, "ocr_scanned_pdfs", True)
    monkeypatch.setattr(settings, "ocr_min_chars", 100)
    monkeypatch.setattr(PDFExtractor, "_extract_text", staticmethod(lambda p: "tiny"))
    monkeypatch.setattr(pdf_mod, "ocr_pdf_pages", lambda p: "OCR RECOVERED TEXT")

    out = PDFExtractor().extract(Path("scanned.pdf"))

    assert "OCR RECOVERED TEXT" in out


def test_pdf_ocr_skipped_when_text_is_rich(monkeypatch):
    monkeypatch.setattr(settings, "extract_tables", False)
    monkeypatch.setattr(settings, "ocr_scanned_pdfs", True)
    monkeypatch.setattr(settings, "ocr_min_chars", 100)
    monkeypatch.setattr(PDFExtractor, "_extract_text", staticmethod(lambda p: "x" * 300))

    def _boom(p):
        raise AssertionError("OCR must not run on a text-rich PDF")

    monkeypatch.setattr(pdf_mod, "ocr_pdf_pages", _boom)

    out = PDFExtractor().extract(Path("digital.pdf"))
    assert len(out) >= 300


def test_extract_pdf_tables_without_pdfplumber_returns_empty(monkeypatch):
    real_import = builtins.__import__

    def _no_pdfplumber(name, *args, **kwargs):
        if name == "pdfplumber":
            raise ImportError("no pdfplumber")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_pdfplumber)
    assert ocr_mod.extract_pdf_tables(Path("x.pdf")) == ""


def test_ocr_pdf_pages_without_pymupdf_returns_empty(monkeypatch):
    real_import = builtins.__import__

    def _no_fitz(name, *args, **kwargs):
        if name == "fitz":
            raise ImportError("no pymupdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_fitz)
    assert ocr_mod.ocr_pdf_pages(Path("x.pdf")) == ""


def test_image_extractor_without_ocr_raises_clear_error(monkeypatch):
    real_import = builtins.__import__

    def _no_pil(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("no Pillow")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_pil)
    with pytest.raises(IngestionError, match="vision"):
        ImageExtractor().extract(Path("photo.png"))
