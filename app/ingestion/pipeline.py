import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.core.exceptions import IngestionError
from app.db.qdrant_store import QdrantStore
from app.ingestion.chunkers.hierarchical import hierarchical_chunk
from app.ingestion.loaders import get_extractor
from app.models.schemas import ChunkMetadata, IngestRequest
from app.retrieval.embedder import Embedder, SparseEmbedder


def checksum(text: str) -> str:
    """Stable content hash, used for ingestion idempotency."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_file_text(file_path: Path) -> str:
    """Extract text from a file (format dispatched by extension)."""
    raw_text = get_extractor(file_path).extract(file_path)
    if not raw_text.strip():
        raise IngestionError(f"No text extracted from {file_path}")
    return raw_text


class IngestionPipeline:
    def __init__(self) -> None:
        self.store = QdrantStore()
        self.embedder = Embedder()
        self.sparse_embedder = SparseEmbedder()

    def _ingest(
        self, text: str, request: IngestRequest, doc_id: UUID | None, default_title: str | None
    ) -> tuple[UUID, int]:
        doc_id = doc_id or uuid4()
        metadata = ChunkMetadata(
            doc_id=doc_id,
            chunk_index=0,
            source=request.source,
            title=request.title or default_title,
            created_at=datetime.now(tz=UTC),
            tags=request.tags,
            checksum=checksum(text),
            tenant_id=request.tenant_id,
            collection_id=request.collection_id,
        )

        chunks = hierarchical_chunk(text, doc_id=doc_id, metadata=metadata)
        chunks = self.embedder.embed_chunks(chunks)
        chunks = self.sparse_embedder.embed_chunks(chunks)
        self.store.upsert_chunks(chunks)

        return doc_id, len(chunks)

    def ingest_file(
        self, file_path: Path, request: IngestRequest, doc_id: UUID | None = None
    ) -> tuple[UUID, int]:
        return self._ingest(
            extract_file_text(file_path), request, doc_id, default_title=file_path.name
        )

    def ingest_text(
        self, text: str, request: IngestRequest, doc_id: UUID | None = None
    ) -> tuple[UUID, int]:
        return self._ingest(text, request, doc_id, default_title=None)
