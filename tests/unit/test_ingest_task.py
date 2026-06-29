from uuid import uuid4

import pytest

from app.ingestion.tasks import _process

DOC_ID = str(uuid4())
REQUEST = {"source": "s", "title": "t", "tags": [], "tenant_id": "acme", "collection_id": None}


class _RecordingStore:
    def __init__(self):
        self.transitions = []

    def set_status(self, doc_id, status, **fields):
        self.transitions.append((status, fields))


class _OkPipeline:
    def ingest_text(self, text, request, doc_id=None):
        return doc_id, 4


class _BoomPipeline:
    def ingest_text(self, text, request, doc_id=None):
        raise RuntimeError("embedding exploded")


def test_process_marks_ready_with_chunk_count():
    store = _RecordingStore()
    _process(DOC_ID, "some text", REQUEST, store, _OkPipeline())

    statuses = [s for s, _ in store.transitions]
    assert statuses == ["processing", "ready"]
    assert store.transitions[-1][1]["chunk_count"] == 4


def test_process_marks_failed_and_reraises():
    store = _RecordingStore()
    with pytest.raises(RuntimeError):
        _process(DOC_ID, "some text", REQUEST, store, _BoomPipeline())

    assert store.transitions[0][0] == "processing"
    assert store.transitions[-1][0] == "failed"
    assert "embedding exploded" in store.transitions[-1][1]["error"]
