"""QdrantStore encrypts chunk text at rest (the payload) and decrypts on read."""

from uuid import uuid4

import pytest

from app.core import crypto
from app.db.qdrant_store import QdrantStore
from app.models.schemas import ChunkMetadata, DocumentChunk


@pytest.fixture(autouse=True)
def _enable_encryption(monkeypatch):
    monkeypatch.setattr(crypto.settings, "app_mode", "local")
    monkeypatch.setattr(crypto.settings, "encryption_key", "vector-store-key")
    monkeypatch.setattr(crypto.settings, "encryption_key_file", False)
    crypto.reset_for_tests()
    yield
    crypto.reset_for_tests()


class _CapturingClient:
    def __init__(self):
        self.upserted = None

    def upsert(self, collection_name, points):
        self.upserted = points


def _store_with_client(client):
    store = QdrantStore.__new__(QdrantStore)  # bypass __init__ (no real Qdrant)
    store.client = client
    store.collection = "test"
    return store


def test_upsert_encrypts_chunk_text_in_payload():
    client = _CapturingClient()
    store = _store_with_client(client)
    chunk = DocumentChunk(
        id=uuid4(),
        text="confidential merger terms",
        embedding=[0.1, 0.2],
        metadata=ChunkMetadata(tenant_id="t1", doc_id=uuid4(), chunk_index=0, source="deal.pdf"),
    )

    store.upsert_chunks([chunk])

    payload = client.upserted[0].payload
    assert payload["text"] != "confidential merger terms"
    assert payload["text"].startswith("enc:v1:")
    assert "confidential" not in payload["text"]
    # Filter/structural metadata stays cleartext so search keeps working.
    assert payload["metadata"]["tenant_id"] == "t1"


def test_to_chunks_decrypts_text():
    store = _store_with_client(_CapturingClient())
    token = crypto.encrypt_field("confidential merger terms")
    point = type(
        "P",
        (),
        {
            "id": str(uuid4()),
            "payload": {
                "text": token,
                "metadata": {
                    "tenant_id": "t1",
                    "doc_id": str(uuid4()),
                    "chunk_index": 0,
                    "source": "s",
                },
            },
            "score": 0.9,
        },
    )()

    chunks = store._to_chunks([point])

    assert chunks[0].text == "confidential merger terms"
    assert chunks[0].score == 0.9
