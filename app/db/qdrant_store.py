import contextlib
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from app.core.config import settings
from app.core.exceptions import RetrievalError
from app.models.schemas import ChunkMetadata, DocumentChunk

# Payload fields we filter by; indexing them keeps tenant/collection/doc queries
# off a full collection scan.
INDEXED_FIELDS = ("tenant_id", "collection_id", "doc_id")


class QdrantStore:
    def __init__(self) -> None:
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        self.collection = settings.qdrant_collection
        self._ensure_collection()
        self._ensure_indexes()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config={
                    "dense": rest.VectorParams(
                        size=1024,
                        distance=rest.Distance.COSINE,
                    )
                },
                sparse_vectors_config={"sparse": rest.SparseVectorParams()},
            )

    def _ensure_indexes(self) -> None:
        """Create keyword payload indexes (idempotent) so filtered search, count,
        and facet over tenant/collection/doc_id use the index instead of scanning.
        Qdrant builds these over any pre-existing points too."""
        for field in INDEXED_FIELDS:
            # Already indexed (or index is building) — safe to ignore.
            with contextlib.suppress(Exception):
                self.client.create_payload_index(
                    collection_name=self.collection,
                    field_name=f"metadata.{field}",
                    field_schema=rest.PayloadSchemaType.KEYWORD,
                )

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return

        points = [
            rest.PointStruct(
                id=str(chunk.id),
                vector=self._build_vectors(chunk),
                payload={
                    "text": chunk.text,
                    "metadata": chunk.metadata.model_dump(mode="json"),
                },
            )
            for chunk in chunks
        ]

        try:
            self.client.upsert(collection_name=self.collection, points=points)
        except Exception as exc:
            raise RetrievalError(f"Qdrant upsert failed: {exc}") from exc

    def _build_vectors(self, chunk: DocumentChunk) -> dict:
        vectors: dict = {"dense": chunk.embedding or []}
        if chunk.sparse_embedding:
            vectors["sparse"] = rest.SparseVector(
                indices=chunk.sparse_embedding["indices"],
                values=chunk.sparse_embedding["values"],
            )
        return vectors

    def search_dense(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[DocumentChunk]:
        return self._query(query_vector, "dense", top_k, filters)

    def search_sparse(
        self,
        indices: list[int],
        values: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[DocumentChunk]:
        sparse = rest.SparseVector(indices=indices, values=values)
        return self._query(sparse, "sparse", top_k, filters)

    def _query(
        self,
        query: Any,
        using: str,
        top_k: int,
        filters: dict | None,
    ) -> list[DocumentChunk]:
        try:
            response = self.client.query_points(
                collection_name=self.collection,
                query=query,
                using=using,
                limit=top_k,
                query_filter=self._build_filter(filters),
                with_payload=True,
            )
        except Exception as exc:
            raise RetrievalError(f"Qdrant {using} search failed: {exc}") from exc

        return self._to_chunks(response.points)

    def _to_chunks(self, points: list) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for point in points:
            payload = point.payload or {}
            meta = payload.get("metadata", {})
            chunk = DocumentChunk(
                id=UUID(str(point.id)),
                text=payload.get("text", ""),
                embedding=None,
                metadata=ChunkMetadata(**meta),
            )
            chunk.score = getattr(point, "score", None)
            chunks.append(chunk)
        return chunks

    def _filter_conditions(self, filters: dict | None) -> list[Any]:
        if not filters:
            return []
        return [
            rest.FieldCondition(key=f"metadata.{key}", match=rest.MatchValue(value=value))
            for key, value in filters.items()
        ]

    def _build_filter(self, filters: dict | None) -> rest.Filter | None:
        conditions = self._filter_conditions(filters)
        return rest.Filter(must=conditions) if conditions else None

    def count_points(self, filters: dict | None = None) -> int:
        """Exact chunk (point) count for the filter — uses the payload index."""
        result = self.client.count(
            collection_name=self.collection,
            count_filter=self._build_filter(filters),
            exact=True,
        )
        return result.count
