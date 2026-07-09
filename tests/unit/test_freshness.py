"""Source freshness/staleness flagging."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.config import settings
from app.models.schemas import ChunkMetadata, DocumentChunk
from app.retrieval.freshness import stale_sources

NOW = datetime(2026, 7, 1, tzinfo=UTC)


def _chunk(source: str, age_days: int, tz: bool = True) -> DocumentChunk:
    created = NOW - timedelta(days=age_days)
    if not tz:
        created = created.replace(tzinfo=None)
    return DocumentChunk(
        id=uuid4(),
        text="t",
        metadata=ChunkMetadata(
            doc_id=uuid4(), chunk_index=0, source=source, created_at=created
        ),
    )


def test_flags_sources_older_than_threshold(monkeypatch):
    monkeypatch.setattr(settings, "stale_after_days", 365)
    chunks = [_chunk("old.pdf", 400), _chunk("fresh.pdf", 30)]
    assert stale_sources(chunks, now=NOW) == ["old.pdf"]


def test_source_is_fresh_if_any_chunk_is_recent(monkeypatch):
    monkeypatch.setattr(settings, "stale_after_days", 365)
    # Same source: one old chunk, one recent — the recent one keeps it fresh.
    chunks = [_chunk("doc.pdf", 400), _chunk("doc.pdf", 10)]
    assert stale_sources(chunks, now=NOW) == []


def test_disabled_when_threshold_zero(monkeypatch):
    monkeypatch.setattr(settings, "stale_after_days", 0)
    assert stale_sources([_chunk("old.pdf", 9999)], now=NOW) == []


def test_naive_created_at_is_treated_as_utc(monkeypatch):
    monkeypatch.setattr(settings, "stale_after_days", 100)
    assert stale_sources([_chunk("old.pdf", 200, tz=False)], now=NOW) == ["old.pdf"]


def test_missing_created_at_is_not_flagged(monkeypatch):
    monkeypatch.setattr(settings, "stale_after_days", 100)
    chunk = DocumentChunk(
        id=uuid4(),
        text="t",
        metadata=ChunkMetadata(doc_id=uuid4(), chunk_index=0, source="x.pdf"),
    )
    assert stale_sources([chunk], now=NOW) == []
