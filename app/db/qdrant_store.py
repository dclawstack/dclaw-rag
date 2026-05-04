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
                vectors_config=rest.VectorParams(
                    size=1024,
                    distance=rest.Distance.COSINE,
                ),
            )

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return

        points = [
            rest.PointStruct(
                id=str(chunk.id),
                vector=chunk.embedding or [],
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

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[DocumentChunk]:
        try:
            qdrant_filter = self._build_filter(filters)
            results = self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
            )
        except Exception as exc:
            raise RetrievalError(f"Qdrant search failed: {exc}") from exc

        chunks: list[DocumentChunk] = []
        for point in results:
            payload = point.payload or {}
            meta = payload.get("metadata", {})
            chunks.append(
                DocumentChunk(
                    id=UUID(point.id),
                    text=payload.get("text", ""),
                    embedding=None,
                    metadata=ChunkMetadata(**meta),
                )
            )
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
