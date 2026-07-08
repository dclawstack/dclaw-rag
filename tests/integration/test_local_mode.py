"""Local-mode end-to-end: the full API booted with ZERO external services —
SQLite LocalKV, embedded Qdrant, inline (thread) ingestion, real embedding +
reranker models. Only the LLM is stubbed (it's an external service).

Heavy (downloads bge-small + bm25 + reranker on first run), so it is gated
behind LOCAL_MODE_E2E=1 and runs in its own CI job, not the main suite.
"""

import asyncio
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("LOCAL_MODE_E2E"),
    reason="local-mode e2e downloads embedding/reranker models; set LOCAL_MODE_E2E=1",
)

FACT_TEXT = (
    "The Zephyr-7 wind turbine uses a magnetic bearing system, which eliminates "
    "the need for oil lubrication entirely. Its rotor diameter is 164 meters and "
    "it is rated at 9.5 megawatts. The magnetic bearings are monitored by an "
    "array of hall-effect sensors that report shaft displacement every millisecond."
)
QUESTION = "What bearing system does the Zephyr-7 turbine use?"

# Cached app.state deps that must be rebuilt against the local backends.
_STATE_DEPS = (
    "searcher",
    "pipeline",
    "store",
    "collection_store",
    "api_key_store",
    "document_store",
    "user_store",
    "refresh_token_store",
    "usage_store",
    "query_cache",
    "rate_limiter",
    "llm",
    "transcriber",
)


class _StubLLM:
    """Deterministic stand-in for the one genuinely external dependency."""

    async def complete(self, messages: list[dict], temperature: float = 0.2) -> str:
        return (
            '{"answer": "The Zephyr-7 uses a magnetic bearing system, which '
            'removes the need for oil lubrication. [1]", '
            '"citations": [1], "confidence": "high"}'
        )


@pytest.fixture
def local_mode(tmp_path, monkeypatch):
    from app.api.dependencies import get_llm
    from app.api.main import app
    from app.core.config import settings
    from app.db import backend

    monkeypatch.setattr(settings, "app_mode", "local")
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "embedding_model", "BAAI/bge-small-en-v1.5")
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)

    backend.reset_backends_for_tests()
    for attr in _STATE_DEPS:
        if hasattr(app.state, attr):
            delattr(app.state, attr)
    app.dependency_overrides[get_llm] = lambda: _StubLLM()

    yield

    backend.reset_backends_for_tests()  # releases the embedded-Qdrant dir lock
    for attr in _STATE_DEPS:
        if hasattr(app.state, attr):
            delattr(app.state, attr)


async def _wait_until_processed(client, doc_id: str, timeout_s: float = 600.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while True:
        resp = await client.get(f"/api/v1/rag/documents/{doc_id}")
        assert resp.status_code == 200
        doc = resp.json()
        if doc["status"] in ("ready", "failed"):
            return doc
        assert asyncio.get_event_loop().time() < deadline, "ingestion timed out"
        await asyncio.sleep(0.5)


async def test_local_mode_ingest_query_roundtrip(local_mode, client):
    # Readiness reports the local backends, no Redis/Qdrant servers running.
    ready = await client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"] == {"kv": True, "qdrant": True}

    # Ingest: registered as pending, processed inline on the background thread.
    resp = await client.post(
        "/api/v1/rag/documents/text",
        json={"text": FACT_TEXT, "metadata": {"source": "e2e", "title": "Zephyr-7 spec"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"

    doc = await _wait_until_processed(client, body["doc_id"])
    assert doc["status"] == "ready", doc.get("error")
    assert doc["chunk_count"] >= 1

    # Query: hybrid retrieval + rerank against the embedded Qdrant, stub LLM.
    resp = await client.post(
        "/api/v1/rag/query", json={"question": QUESTION, "top_k": 3, "verify": False}
    )
    assert resp.status_code == 200
    answer = resp.json()
    assert answer["abstained"] is False
    assert "magnetic bearing" in answer["answer"]
    assert answer["citations"], "expected at least one citation"
    assert "Zephyr-7" in answer["citations"][0]["text"]

    # The ingested state actually lives in the local data dir.
    from app.core.config import settings

    assert settings.sqlite_path.exists()
    assert settings.qdrant_path.exists()

    # --- audio: ingest a spoken fact as a document (whisper transcription) ---
    with open("tests/fixtures/aurora_fact.mp3", "rb") as fh:
        resp = await client.post(
            "/api/v1/rag/documents/upload",
            files={"file": ("aurora_fact.mp3", fh.read(), "audio/mpeg")},
            data={"metadata": '{"source": "e2e-audio", "title": "Aurora dam memo"}'},
        )
    assert resp.status_code == 200
    doc = await _wait_until_processed(client, resp.json()["doc_id"])
    assert doc["status"] == "ready", doc.get("error")

    resp = await client.post(
        "/api/v1/rag/query",
        json={"question": "How much power does the Aurora dam generate?", "top_k": 3},
    )
    assert resp.status_code == 200
    hits = resp.json()["retrieved_chunks"]
    # Whisper renders the spoken number as "40" or "forty" depending on the
    # host's quantized inference — assert on the stable words instead.
    assert any("megawatts" in c["text"].lower() for c in hits)

    # --- audio: voice query via /transcribe feeding /query ---
    with open("tests/fixtures/voice_query.mp3", "rb") as fh:
        resp = await client.post(
            "/api/v1/rag/transcribe",
            files={"file": ("voice_query.mp3", fh.read(), "audio/mpeg")},
        )
    assert resp.status_code == 200
    transcript = resp.json()["text"]
    assert "bearing" in transcript.lower() and "turbine" in transcript.lower()

    resp = await client.post(
        "/api/v1/rag/query", json={"question": transcript, "top_k": 3, "verify": False}
    )
    assert resp.status_code == 200
    voiced = resp.json()
    assert voiced["abstained"] is False
    assert voiced["citations"]
