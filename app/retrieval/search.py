from app.core.config import settings
from app.db.qdrant_store import QdrantStore
from app.models.schemas import DocumentChunk
from app.retrieval.embedder import Embedder, SparseEmbedder
from app.retrieval.reranker import Reranker


def reciprocal_rank_fusion(
    result_lists: list[list[DocumentChunk]],
    k: int = 60,
) -> list[DocumentChunk]:
    """Fuse ranked result lists with Reciprocal Rank Fusion (deduped by id)."""
    scores: dict[str, float] = {}
    chunk_by_id: dict[str, DocumentChunk] = {}
    for results in result_lists:
        for rank, chunk in enumerate(results):
            cid = str(chunk.id)
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
            chunk_by_id.setdefault(cid, chunk)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [chunk_by_id[cid] for cid, _ in ordered]


class Searcher:
    def __init__(
        self,
        store: QdrantStore | None = None,
        embedder: Embedder | None = None,
        sparse_embedder: SparseEmbedder | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.store = store or QdrantStore()
        self.embedder = embedder or Embedder()
        self.sparse_embedder = sparse_embedder or SparseEmbedder()
        self.reranker = reranker or Reranker()

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[DocumentChunk]:
        candidate_k = max(top_k * 10, settings.hybrid_candidate_k)

        dense_vector = self.embedder.embed_query(query)
        sparse_vector = self.sparse_embedder.embed_query(query)

        dense_hits = self.store.search_dense(dense_vector, candidate_k, filters)
        sparse_hits = self.store.search_sparse(
            sparse_vector["indices"], sparse_vector["values"], candidate_k, filters
        )

        fused = reciprocal_rank_fusion([dense_hits, sparse_hits], k=settings.rrf_k)
        reranked = self.reranker.rerank(query, fused[:candidate_k])
        return reranked[:top_k]
