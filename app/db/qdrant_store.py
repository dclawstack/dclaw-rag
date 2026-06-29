import contextlib
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from app.core.config import settings
from app.core.exceptions import RetrievalError
from app.models.schemas import ChunkMetadata, DocumentChunk

# Payload fields we filter/group by; indexing them keeps tenant/collection/doc
# queries off a full collection scan.
INDEXED_FIELDS = ("tenant_id", "collection_id", "doc_id")

# Upper bound on distinct documents we count or paginate over per filter via the
# doc_id facet. Beyond this, counts/listings are capped (see Phase 5 registry).
DOC_FACET_CAP = 10_000


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

    def _facet_doc_ids(self, filters: dict | None) -> list[str]:
        """Distinct doc_ids matching the filter, via a facet over the indexed
        doc_id field — no full scan. Bounded at DOC_FACET_CAP distinct docs."""
        result = self.client.facet(
            collection_name=self.collection,
            key="metadata.doc_id",
            facet_filter=self._build_filter(filters),
            limit=DOC_FACET_CAP,
            exact=True,
        )
        return [str(hit.value) for hit in result.hits]

    def count_documents(self, filters: dict | None = None) -> int:
        """Count distinct documents (by doc_id) matching the filter."""
        return len(self._facet_doc_ids(filters))

    def list_documents(
        self, filters: dict | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """Return a page of distinct documents (deduped by doc_id) matching the
        filter. Document ids come from the doc_id facet (indexed); only the page's
        metadata is then fetched, so work is bounded by the page, not the corpus."""
        page_ids = self._facet_doc_ids(filters)[offset : offset + limit]
        if not page_ids:
            return []

        scroll_filter = rest.Filter(
            must=[
                *self._filter_conditions(filters),
                rest.FieldCondition(
                    key="metadata.doc_id", match=rest.MatchAny(any=page_ids)
                ),
            ]
        )

        # Fetch metadata for just this page's docs; stop once each is seen once.
        remaining = set(page_ids)
        meta_by_doc: dict[str, dict] = {}
        cursor = None
        while remaining:
            points, cursor = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=scroll_filter,
                with_payload=True,
                with_vectors=False,
                limit=256,
                offset=cursor,
            )
            for point in points:
                meta = (point.payload or {}).get("metadata", {})
                doc_id = meta.get("doc_id")
                if doc_id in remaining:
                    meta_by_doc[doc_id] = {
                        "id": doc_id,
                        "filename": meta.get("title") or meta.get("source") or doc_id,
                        "status": "ready",
                        "created_at": meta.get("created_at") or "",
                    }
                    remaining.discard(doc_id)
            if cursor is None:
                break

        # Preserve facet order for a stable page.
        return [meta_by_doc[doc_id] for doc_id in page_ids if doc_id in meta_by_doc]
