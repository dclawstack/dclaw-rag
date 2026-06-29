"""Celery application for off-request-path work (document ingestion).

Run a worker with:  celery -A app.worker.celery_app worker --queues ingestion
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "dclaw",
    broker=settings.celery_broker_url,
    backend=settings.celery_broker_url,
)
celery_app.conf.update(
    task_default_queue="ingestion",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)

# Ensure task modules are imported so the worker registers them.
celery_app.autodiscover_tasks(["app.ingestion"])
