"""Async document ingestion task.

The heavy work (chunk -> embed -> upsert) runs off the request path on a Celery
worker. `_process` holds the status-transition logic and is pure w.r.t. its
injected store/pipeline, so it can be unit-tested without Celery or real models.
"""

from uuid import UUID

import structlog

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
    from app.db.document_store import DocumentStore
    from app.ingestion.pipeline import IngestionPipeline

    _process(doc_id, text, request_dict, DocumentStore(), IngestionPipeline())
