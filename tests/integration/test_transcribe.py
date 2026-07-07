"""/transcribe route behavior with a stubbed transcriber (the real whisper
model is exercised by the gated local-mode e2e)."""

import pytest

from app.api.main import app
from app.api.routes.transcribe import get_transcriber
from app.core.config import settings

PATH = "/api/v1/rag/transcribe"


class _StubTranscriber:
    def __init__(self):
        self.calls = []

    def transcribe(self, file_path):
        self.calls.append(str(file_path))
        return "what bearing system does the zephyr seven use"


@pytest.fixture
def stub():
    t = _StubTranscriber()
    app.dependency_overrides[get_transcriber] = lambda: t
    return t


async def test_transcribe_returns_text(client, stub):
    resp = await client.post(
        PATH, files={"file": ("clip.webm", b"fake-audio-bytes", "audio/webm")}
    )
    assert resp.status_code == 200
    assert resp.json() == {"text": "what bearing system does the zephyr seven use"}
    assert len(stub.calls) == 1
    assert stub.calls[0].endswith(".webm")


async def test_transcribe_rejects_empty_upload(client, stub):
    resp = await client.post(PATH, files={"file": ("clip.webm", b"", "audio/webm")})
    assert resp.status_code == 400
    assert not stub.calls


async def test_transcribe_rejects_oversized_upload(client, stub, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    resp = await client.post(
        PATH, files={"file": ("clip.webm", b"x" * 11, "audio/webm")}
    )
    assert resp.status_code == 413
    assert not stub.calls


async def test_transcribe_requires_auth(client, stub):
    from app.api.dependencies import get_principal

    app.dependency_overrides.pop(get_principal, None)  # drop the test auth bypass
    resp = await client.post(
        PATH, files={"file": ("clip.webm", b"fake", "audio/webm")}
    )
    assert resp.status_code == 401
