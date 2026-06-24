from uuid import UUID

from app.models.schemas import ChunkMetadata, DocumentChunk
from app.retrieval.search import Searcher


def _chunk(n: int) -> DocumentChunk:
    return DocumentChunk(
        id=UUID(int=n),
        text=f"c{n}",
        metadata=ChunkMetadata(doc_id=UUID(int=0), chunk_index=n, source="t"),
    )


class _FakeStore:
    def __init__(self, dense, sparse):
        self._dense = dense
        self._sparse = sparse
        self.dense_called = False
        self.sparse_called = False

    def search_dense(self, query_vector, top_k=10, filters=None):
        self.dense_called = True
        return self._dense

    def search_sparse(self, indices, values, top_k=10, filters=None):
        self.sparse_called = True
        return self._sparse


class _FakeEmbedder:
    def embed_query(self, query):
        return [0.1, 0.2]


class _FakeSparseEmbedder:
    def embed_query(self, query):
        return {"indices": [1, 2], "values": [0.5, 0.5]}


class _FakeReranker:
    def __init__(self):
        self.seen = None

    def rerank(self, query, chunks):
        self.seen = chunks
        return chunks


def test_searcher_queries_both_indexes_and_fuses():
    a, b, c = _chunk(1), _chunk(2), _chunk(3)
    store = _FakeStore(dense=[a, b], sparse=[b, c])
    reranker = _FakeReranker()
    searcher = Searcher(
        store=store,
        embedder=_FakeEmbedder(),
        sparse_embedder=_FakeSparseEmbedder(),
        reranker=reranker,
    )

    out = searcher.search("q", top_k=2)

    assert store.dense_called and store.sparse_called
    # the reranker receives the fused, deduped candidate set (a, b, c)
    assert {str(x.id) for x in reranker.seen} == {str(a.id), str(b.id), str(c.id)}
    # b appears in both lists -> ranked first; top_k truncates to 2
    assert len(out) == 2
    assert str(out[0].id) == str(b.id)
