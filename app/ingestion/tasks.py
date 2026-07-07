"""Async document ingestion task.

The heavy work (chunk -> embed -> upsert) runs off the request path — on a
Celery worker in server mode, or on a single background thread in local mode
(`dispatch_ingestion` picks). `_process` holds the status-transition logic and
is pure w.r.t. its injected store/pipeline, so it can be unit-tested without
Celery or real models.
"""

import contextlib
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import structlog

from app.core.config import settings
from app.worker import celery_app

logger = structlog.get_logger(__name__)


def _process(doc_id: str, text: str, request_dict: dict, store, pipeline) -> None:
    from app.models.schemas import IngestRequest

    store.set_status(doc_id, "processing")
    try:
        _, chunks_inserted = pipeline.ingest_text(
            text, IngestRequest(**request_dict), doc_id=UUID(doc_id)
        )
    except Exception as exc:
        logger.error("ingestion_failed", doc_id=doc_id, error=str(exc))
        store.set_status(doc_id, "failed", error=str(exc))
        raise
    store.set_status(doc_id, "ready", chunk_count=chunks_inserted, error=None)
    logger.info("ingestion_complete", doc_id=doc_id, chunks=chunks_inserted)


@celery_app.task(name="ingest_document", bind=True, max_retries=2, default_retry_delay=10)
def ingest_document_task(self, doc_id: str, text: str, request_dict: dict) -> None:
    from app.ingestion.pipeline import IngestionPipeline

    _process_and_invalidate(doc_id, text, request_dict, IngestionPipeline())


def _process_and_invalidate(doc_id: str, text: str, request_dict: dict, pipeline) -> None:
    from app.db.document_store import DocumentStore
    from app.db.query_cache import QueryCache

    _process(doc_id, text, request_dict, DocumentStore(), pipeline)

    # New chunks are now queryable — invalidate the tenant's cached answers.
    tenant = request_dict.get("tenant_id")
    if tenant:
        with contextlib.suppress(Exception):
            QueryCache().bump_version(tenant)


# Local mode: ingestion runs on one background thread instead of Celery. A
# single worker keeps the pipeline (and its models) loaded once and serializes
# writes to the embedded Qdrant; the status lifecycle is identical.
_local_executor: ThreadPoolExecutor | None = None
_local_pipeline = None


def _run_local(doc_id: str, text: str, request_dict: dict) -> None:
    global _local_pipeline
    if _local_pipeline is None:
        from app.ingestion.pipeline import IngestionPipeline

        _local_pipeline = IngestionPipeline()
    # _process has already recorded a failed status + logged on error.
    with contextlib.suppress(Exception):
        _process_and_invalidate(doc_id, text, request_dict, _local_pipeline)


def dispatch_ingestion(doc_id: str, text: str, request_dict: dict) -> None:
    """Hand a registered (pending) document to the async worker for this mode."""
    if settings.app_mode == "local":
        global _local_executor
        if _local_executor is None:
            _local_executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="local-ingest"
            )
        _local_executor.submit(_run_local, doc_id, text, request_dict)
    else:
        ingest_document_task.delay(doc_id, text, request_dict)
