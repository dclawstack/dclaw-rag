"""Prometheus metrics. Collectors are module-level singletons; the middleware
records HTTP metrics and routes record domain metrics (e.g. queries)."""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
QUERIES = Counter(
    "rag_queries_total",
    "RAG query requests",
    ["abstained"],
)
INGEST_ENQUEUED = Counter(
    "rag_ingest_enqueued_total",
    "Documents enqueued for ingestion",
)


def render() -> tuple[bytes, str]:
    """Return the metrics exposition payload and its content type."""
    return generate_latest(), CONTENT_TYPE_LATEST
