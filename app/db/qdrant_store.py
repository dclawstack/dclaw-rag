from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from app.core.config import settings
from app.core.exceptions import RetrievalError
from app.models.schemas import ChunkMetadata, DocumentChunk


class QdrantStore:
    def __init__(self) -> None:
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        self.collection = settings.qdrant_collection
        self._ensure_collection()

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
        query: object,
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

    def _build_filter(self, filters: dict | None) -> rest.Filter | None:
        if not filters:
            return None

        conditions: list[rest.FieldCondition] = []
        for key, value in filters.items():
            conditions.append(
                rest.FieldCondition(
                    key=f"metadata.{key}",
                    match=rest.MatchValue(value=value),
                )
            )
        return rest.Filter(must=conditions)

    def count_points(self, filters: dict | None = None) -> int:
        result = self.client.count(
            collection_name=self.collection,
            count_filter=self._build_filter(filters),
            exact=True,
        )
        return result.count

    def list_documents(self, filters: dict | None = None, limit: int = 1000) -> list[dict]:
        """Return distinct documents (deduped by doc_id) matching the filter."""
        qdrant_filter = self._build_filter(filters)
        docs: dict[str, dict] = {}
        offset = None
        while len(docs) < limit:
            points, offset = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=qdrant_filter,
                with_payload=True,
                with_vectors=False,
                limit=256,
                offset=offset,
            )
            for point in points:
                meta = (point.payload or {}).get("metadata", {})
                doc_id = meta.get("doc_id")
                if doc_id and doc_id not in docs:
                    docs[doc_id] = {
                        "id": doc_id,
                        "filename": meta.get("title") or meta.get("source") or doc_id,
                        "status": "ready",
                        "created_at": meta.get("created_at") or "",
                    }
            if offset is None:
                break
        return list(docs.values())

    def delete_by_doc_id(self, doc_id: UUID) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="metadata.doc_id",
                        match=rest.MatchValue(value=str(doc_id)),
                    )
                ]
            ),
        )
