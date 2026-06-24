import pytest

from app.core.exceptions import IngestionError
from app.ingestion.extractors.csv import CSVExtractor
from app.ingestion.extractors.docx import DocxExtractor
from app.ingestion.extractors.html import HTMLExtractor
from app.ingestion.extractors.markdown import MarkdownExtractor
from app.ingestion.extractors.pdf import PDFExtractor
from app.ingestion.extractors.text import PlainTextExtractor
from app.ingestion.loaders import get_extractor


@pytest.mark.parametrize(
    "name,expected",
    [
        ("a.pdf", PDFExtractor),
        ("a.md", MarkdownExtractor),
        ("a.markdown", MarkdownExtractor),
        ("a.txt", MarkdownExtractor),
        ("a.html", HTMLExtractor),
        ("a.htm", HTMLExtractor),
        ("a.csv", CSVExtractor),
        ("a.tsv", CSVExtractor),
        ("a.docx", DocxExtractor),
        ("a.json", PlainTextExtractor),
        ("a.yaml", PlainTextExtractor),
        ("a.log", PlainTextExtractor),
    ],
)
def test_get_extractor_dispatch(tmp_path, name, expected):
    assert isinstance(get_extractor(tmp_path / name), expected)


def test_get_extractor_is_case_insensitive(tmp_path):
    assert isinstance(get_extractor(tmp_path / "REPORT.HTML"), HTMLExtractor)


def test_get_extractor_unknown_raises(tmp_path):
    with pytest.raises(IngestionError):
        get_extractor(tmp_path / "a.xyz")


def test_html_extractor_strips_markup_and_scripts(tmp_path):
    f = tmp_path / "page.html"
    f.write_text(
        "<html><head><style>x{}</style></head>"
        "<body><h1>Title</h1><script>alert(1)</script><p>Hello world</p></body></html>"
    )
    text = HTMLExtractor().extract(f)
    assert "Title" in text
    assert "Hello world" in text
    assert "alert" not in text
    assert "<p>" not in text


def test_csv_extractor_flattens_rows(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("name,role\nAlice,eng\nBob,design\n")
    text = CSVExtractor().extract(f)
    assert "name | role" in text
    assert "Alice | eng" in text


def test_csv_extractor_handles_tsv(tmp_path):
    f = tmp_path / "data.tsv"
    f.write_text("a\tb\n1\t2\n")
    text = CSVExtractor().extract(f)
    assert "a | b" in text
    assert "1 | 2" in text


def test_plaintext_extractor_reads_content(tmp_path):
    f = tmp_path / "notes.log"
    f.write_text("line one\nline two")
    assert PlainTextExtractor().extract(f) == "line one\nline two"


def test_docx_extractor_roundtrip(tmp_path):
    docx = pytest.importorskip("docx")
    path = tmp_path / "doc.docx"
    document = docx.Document()
    document.add_paragraph("First paragraph.")
    document.add_paragraph("Second paragraph.")
    document.save(str(path))

    text = DocxExtractor().extract(path)
    assert "First paragraph." in text
    assert "Second paragraph." in text
