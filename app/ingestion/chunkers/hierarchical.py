from uuid import UUID, uuid4

from app.models.schemas import ChunkMetadata, DocumentChunk

DEFAULT_PARENT_SIZE = 1024
DEFAULT_CHILD_SIZE = 256
DEFAULT_OVERLAP = 50


def hierarchical_chunk(
    text: str,
    doc_id: UUID,
    metadata: ChunkMetadata,
    parent_size: int = DEFAULT_PARENT_SIZE,
    child_size: int = DEFAULT_CHILD_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[DocumentChunk]:
    """Create parent-child chunks."""
    chunks: list[DocumentChunk] = []
    parent_id = uuid4()
    parent_text = ""

    words = text.split()

    for child_index, i in enumerate(range(0, len(words), child_size - overlap)):
        child_words = words[i : i + child_size]
        child_text = " ".join(child_words)

        chunk = DocumentChunk(
            id=uuid4(),
            text=child_text,
            embedding=None,
            metadata=ChunkMetadata(
                doc_id=doc_id,
                chunk_index=child_index,
                parent_id=parent_id,
                source=metadata.source,
                title=metadata.title,
                created_at=metadata.created_at,
                tags=metadata.tags,
                checksum=metadata.checksum,
                tenant_id=metadata.tenant_id,
                collection_id=metadata.collection_id,
            ),
        )
        chunks.append(chunk)

        parent_text += " " + child_text
        if len(parent_text.split()) >= parent_size:
            parent_id = uuid4()
            parent_text = ""

    return chunks
