from app.core.config import settings
from app.db.qdrant_store import QdrantStore
from app.models.schemas import DocumentChunk
from app.retrieval.embedder import Embedder
from app.retrieval.reranker import Reranker


class Searcher:
    def __init__(self) -> None:
        self.store = QdrantStore()
        self.embedder = Embedder()
        self.reranker = Reranker()

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[DocumentChunk]:
        query_vector = self.embedder.embed_query(query)
        candidates = self.store.search(
            query_vector=query_vector,
            top_k=max(top_k * 10, 100),
            filters=filters,
        )
        reranked = self.reranker.rerank(query, candidates)
        return reranked[:top_k]
