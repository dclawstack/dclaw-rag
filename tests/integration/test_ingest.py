from uuid import uuid4

from app.api.dependencies import get_pipeline
from app.api.main import app

UPLOAD_PATH = "/api/v1/rag/documents/upload"
TEXT_PATH = "/api/v1/rag/documents/text"


class _FakePipeline:
    def __init__(self):
        self.last_request = None

    def ingest_file(self, file_path, request):
        self.last_request = request
        return uuid4(), 5

    def ingest_text(self, text, request):
        self.last_request = request
        return uuid4(), 3


async def test_ingest_text_reports_chunk_count(client):
    pipeline = _FakePipeline()
    app.dependency_overrides[get_pipeline] = lambda: pipeline

    resp = await client.post(
        TEXT_PATH,
        json={"text": "hello world", "metadata": {"source": "unit", "title": "t", "tags": ["a"]}},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["chunks_inserted"] == 3
    assert body["status"] == "success"
    assert body["doc_id"]
    assert pipeline.last_request.source == "unit"
    assert pipeline.last_request.tags == ["a"]


async def test_upload_parses_metadata_blob(client):
    pipeline = _FakePipeline()
    app.dependency_overrides[get_pipeline] = lambda: pipeline

    files = {"file": ("notes.md", b"# Title\n\nbody text", "text/markdown")}
    data = {"metadata": '{"source": "unit", "tags": ["x"]}'}
    resp = await client.post(UPLOAD_PATH, files=files, data=data)

    assert resp.status_code == 200
    body = resp.json()
    assert body["chunks_inserted"] == 5
    assert pipeline.last_request.source == "unit"
    # title falls back to the filename when not provided in metadata
    assert pipeline.last_request.title == "notes.md"
