"""Source freshness / staleness tracking (E4.11).

Retrieved chunks carry their document's `created_at`; this flags the distinct
sources whose newest retrieved chunk is older than `stale_after_days`, so the UI
can warn that an answer may be leaning on out-of-date material.
"""

from datetime import UTC, datetime

from app.core.config import settings
from app.models.schemas import DocumentChunk


def stale_sources(chunks: list[DocumentChunk], now: datetime | None = None) -> list[str]:
    """Distinct source names whose retrieved content is older than the threshold.

    A source is considered fresh if ANY of its retrieved chunks is within the
    window (so a recently-updated document isn't flagged on an old chunk).
    """
    if settings.stale_after_days <= 0:
        return []
    now = now or datetime.now(tz=UTC)
    cutoff_seconds = settings.stale_after_days * 86400

    freshest: dict[str, float] = {}  # source -> smallest age in seconds seen
    for chunk in chunks:
        created = chunk.metadata.created_at
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        age = (now - created).total_seconds()
        source = chunk.metadata.source
        freshest[source] = min(freshest.get(source, age), age)

    return sorted(src for src, age in freshest.items() if age > cutoff_seconds)
