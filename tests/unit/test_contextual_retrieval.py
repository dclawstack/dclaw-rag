"""Contextual retrieval: chunks carry situating context that is embedded (not
stored), and the toggle disables it."""

from uuid import uuid4

from app.core.config import settings
from app.ingestion.chunkers.hierarchical import build_chunk_context, hierarchical_chunk
from app.models.schemas import ChunkMetadata
from app.retrieval.embedder import embedding_text


def _meta(title=None, source="report.pdf"):
    return ChunkMetadata(doc_id=uuid4(), chunk_index=0, source=source, title=title)


def test_context_uses_title_then_source(monkeypatch):
    monkeypatch.setattr(settings, "contextual_retrieval", True)
    assert build_chunk_context(_meta(title="Q3 Earnings")) == "Document: Q3 Earnings"
    assert build_chunk_context(_meta(title=None, source="deal.pdf")) == "Document: deal.pdf"


def test_context_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "contextual_retrieval", False)
    assert build_chunk_context(_meta(title="Q3 Earnings")) is None


def test_embedding_text_prepends_context_but_not_stored(monkeypatch):
    monkeypatch.setattr(settings, "contextual_retrieval", True)
    doc_id = uuid4()
    chunks = hierarchical_chunk(
        "alpha beta gamma delta", doc_id=doc_id, metadata=_meta(title="Physics Notes")
    )
    chunk = chunks[0]

    # Stored/displayed text is the raw chunk; context lives separately.
    assert "Document:" not in chunk.text
    assert chunk.context == "Document: Physics Notes"
    # The embedded text situates the chunk in its document.
    embedded = embedding_text(chunk)
    assert embedded.startswith("Document: Physics Notes")
    assert chunk.text in embedded


def test_embedding_text_without_context_is_raw(monkeypatch):
    monkeypatch.setattr(settings, "contextual_retrieval", False)
    chunks = hierarchical_chunk("alpha beta gamma", doc_id=uuid4(), metadata=_meta())
    chunk = chunks[0]
    assert chunk.context is None
    assert embedding_text(chunk) == chunk.text
