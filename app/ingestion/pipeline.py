from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.core.exceptions import IngestionError
from app.db.qdrant_store import QdrantStore
from app.ingestion.chunkers.hierarchical import hierarchical_chunk
from app.ingestion.loaders import get_extractor
from app.models.schemas import ChunkMetadata, DocumentChunk, IngestRequest
from app.retrieval.embedder import Embedder


class IngestionPipeline:
    def __init__(self) -> None:
        self.store = QdrantStore()
        self.embedder = Embedder()

    def ingest_file(self, file_path: Path, request: IngestRequest) -> tuple[UUID, int]:
        extractor = get_extractor(file_path)
        raw_text = extractor.extract(file_path)

        if not raw_text.strip():
            raise IngestionError(f"No text extracted from {file_path}")

        doc_id = uuid4()
        metadata = ChunkMetadata(
            doc_id=doc_id,
            chunk_index=0,
            source=request.source,
            title=request.title or file_path.name,
            created_at=datetime.now(tz=timezone.utc),
            tags=request.tags,
            checksum=None,
            tenant_id=request.tenant_id,
        )

        chunks = hierarchical_chunk(raw_text, doc_id=doc_id, metadata=metadata)
        chunks = self.embedder.embed_chunks(chunks)
        self.store.upsert_chunks(chunks)

        return doc_id, len(chunks)

    def ingest_text(self, text: str, request: IngestRequest) -> tuple[UUID, int]:
        doc_id = uuid4()
        metadata = ChunkMetadata(
            doc_id=doc_id,
            chunk_index=0,
            source=request.source,
            title=request.title,
            created_at=datetime.now(tz=timezone.utc),
            tags=request.tags,
            checksum=None,
            tenant_id=request.tenant_id,
        )

        chunks = hierarchical_chunk(text, doc_id=doc_id, metadata=metadata)
        chunks = self.embedder.embed_chunks(chunks)
        self.store.upsert_chunks(chunks)

        return doc_id, len(chunks)
