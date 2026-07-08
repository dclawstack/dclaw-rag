from uuid import UUID, uuid4

from app.core.config import settings
from app.models.schemas import ChunkMetadata, DocumentChunk

DEFAULT_PARENT_SIZE = 1024
DEFAULT_CHILD_SIZE = 256
DEFAULT_OVERLAP = 50


def build_chunk_context(metadata: ChunkMetadata) -> str | None:
    """Cheap situating context for contextual retrieval: the document title
    (falling back to the source name). Prepended to the chunk only at embedding
    time so its vector reflects which document it belongs to. Returns None when
    disabled or when there's nothing useful to add."""
    if not settings.contextual_retrieval:
        return None
    label = metadata.title or metadata.source
    return f"Document: {label}" if label else None


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
    context = build_chunk_context(metadata)

    for child_index, i in enumerate(range(0, len(words), child_size - overlap)):
        child_words = words[i : i + child_size]
        child_text = " ".join(child_words)

        chunk = DocumentChunk(
            id=uuid4(),
            text=child_text,
            context=context,
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
