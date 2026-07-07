import pytest

from app.core.exceptions import IngestionError
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
        ("a.pptx", PptxExtractor),
        ("a.xlsx", XlsxExtractor),
        ("a.epub", EpubExtractor),
        ("a.eml", EmailExtractor),
        ("a.rtf", RTFExtractor),
        ("a.json", PlainTextExtractor),
        ("a.yaml", PlainTextExtractor),
        ("a.log", PlainTextExtractor),
    ],
)
def test_get_extractor_dispatch(tmp_path, name, expected):
    assert isinstance(get_extractor(tmp_path / name), expected)


def test_get_extractor_is_case_insensitive(tmp_path):
    assert isinstance(get_extractor(tmp_path / "REPORT.HTML"), HTMLExtractor)


def test_get_extractor_unknown_binary_raises(tmp_path):
    f = tmp_path / "blob.xyz"
    f.write_bytes(b"\x00\x01\x02binary")
    with pytest.raises(IngestionError):
        get_extractor(f)


def test_get_extractor_missing_unknown_file_raises(tmp_path):
    with pytest.raises(IngestionError):
        get_extractor(tmp_path / "a.xyz")


def test_get_extractor_falls_back_to_plaintext_for_unknown_text(tmp_path):
    for name, content in [
        ("main.tex", "\\section{Intro} hello"),
        ("script.py", "print('hi')"),
        ("Makefile", "all:\n\techo hi"),
    ]:
        f = tmp_path / name
        f.write_text(content)
        assert isinstance(get_extractor(f), PlainTextExtractor)


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


def test_pptx_extractor_roundtrip(tmp_path):
    pptx = pytest.importorskip("pptx")
    path = tmp_path / "deck.pptx"
    pres = pptx.Presentation()
    slide = pres.slides.add_slide(pres.slide_layouts[1])
    slide.shapes.title.text = "Quarterly Review"
    slide.placeholders[1].text = "Revenue grew 12 percent"
    pres.save(str(path))

    text = PptxExtractor().extract(path)
    assert "Quarterly Review" in text
    assert "Revenue grew 12 percent" in text


def test_xlsx_extractor_roundtrip(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "book.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Budget"
    ws.append(["item", "cost"])
    ws.append(["laptop", 1200])
    ws.append([None, None])  # empty row is skipped
    wb.save(str(path))

    text = XlsxExtractor().extract(path)
    assert "# Budget" in text
    assert "item | cost" in text
    assert "laptop | 1200" in text


def test_epub_extractor_roundtrip(tmp_path):
    pytest.importorskip("ebooklib")
    from ebooklib import epub

    path = tmp_path / "book.epub"
    book = epub.EpubBook()
    book.set_identifier("id1")
    book.set_title("Test Book")
    chapter = epub.EpubHtml(title="Ch1", file_name="ch1.xhtml")
    chapter.content = "<html><body><h1>Chapter One</h1><p>Once upon a time.</p></body></html>"
    book.add_item(chapter)
    book.spine = [chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    epub.write_epub(str(path), book)

    text = EpubExtractor().extract(path)
    assert "Chapter One" in text
    assert "Once upon a time." in text


def test_email_extractor_plain_body_and_headers(tmp_path):
    path = tmp_path / "mail.eml"
    path.write_text(
        "From: alice@example.com\n"
        "To: bob@example.com\n"
        "Subject: Deploy schedule\n"
        "Content-Type: text/plain\n"
        "\n"
        "The deploy happens Friday at noon.\n"
    )
    text = EmailExtractor().extract(path)
    assert "Subject: Deploy schedule" in text
    assert "The deploy happens Friday at noon." in text


def test_email_extractor_html_body_is_stripped(tmp_path):
    path = tmp_path / "mail.eml"
    path.write_text(
        "From: alice@example.com\n"
        "Subject: HTML mail\n"
        'Content-Type: text/html; charset="utf-8"\n'
        "\n"
        "<html><body><p>Rich <b>content</b> here</p></body></html>\n"
    )
    text = EmailExtractor().extract(path)
    assert "Rich" in text and "content" in text and "here" in text
    assert "<p>" not in text


def test_rtf_extractor_strips_control_words(tmp_path):
    path = tmp_path / "doc.rtf"
    path.write_text(r"{\rtf1\ansi\deff0 {\b Bold headline} and plain body.}")
    text = RTFExtractor().extract(path)
    assert "Bold headline" in text
    assert "plain body" in text
    assert "\\rtf1" not in text


def test_audio_extractor_uses_transcriber(tmp_path, monkeypatch):
    from app.ingestion.extractors.audio import AudioExtractor

    class _Stub:
        def transcribe(self, file_path):
            return "spoken words"

    monkeypatch.setattr(
        "app.ingestion.transcriber.get_transcriber", lambda: _Stub()
    )
    f = tmp_path / "memo.mp3"
    f.write_bytes(b"\xff\xfb fake mp3")
    assert AudioExtractor().extract(f) == "spoken words"
    assert isinstance(get_extractor(f), AudioExtractor)
