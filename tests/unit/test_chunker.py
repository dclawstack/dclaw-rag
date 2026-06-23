from uuid import uuid4

from app.ingestion.chunkers.hierarchical import hierarchical_chunk
from app.models.schemas import ChunkMetadata


def _meta(doc_id):
    return ChunkMetadata(doc_id=doc_id, chunk_index=0, source="test")


def test_hierarchical_chunk_splits_long_text():
    doc_id = uuid4()
    text = " ".join(f"word{i}" for i in range(600))
    chunks = hierarchical_chunk(text, doc_id=doc_id, metadata=_meta(doc_id))

    assert len(chunks) > 1
    assert all(c.metadata.doc_id == doc_id for c in chunks)
    assert all(c.text for c in chunks)


def test_hierarchical_chunk_indexes_sequentially():
    doc_id = uuid4()
    text = " ".join(f"word{i}" for i in range(600))
    chunks = hierarchical_chunk(text, doc_id=doc_id, metadata=_meta(doc_id))

    assert [c.metadata.chunk_index for c in chunks] == list(range(len(chunks)))
