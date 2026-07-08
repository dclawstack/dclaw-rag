from app.core.config import settings
from app.models.schemas import DocumentChunk


def embedding_text(chunk: DocumentChunk) -> str:
    """The text actually embedded for a chunk: its situating context (if any,
    from contextual retrieval) prepended to the chunk body. The stored/displayed
    text remains chunk.text."""
    if chunk.context:
        return f"{chunk.context}\n\n{chunk.text}"
    return chunk.text


class Embedder:
    def __init__(self) -> None:
        # Lazy import to avoid loading at import time
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            settings.embedding_model,
            device=settings.embedding_device,
        )
        self.batch_size = settings.embedding_batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [emb.tolist() for emb in embeddings]

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def embed_chunks(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        texts = [embedding_text(c) for c in chunks]
        embeddings = self.embed(texts)
        for chunk, emb in zip(chunks, embeddings, strict=True):
            chunk.embedding = emb
        return chunks


class SparseEmbedder:
    """BM25/sparse embeddings via fastembed for lexical (keyword) retrieval."""

    def __init__(self) -> None:
        # Lazy import to avoid loading at import time
        from fastembed import SparseTextEmbedding

        self.model = SparseTextEmbedding(model_name=settings.sparse_model)

    def embed_query(self, text: str) -> dict[str, list]:
        emb = next(iter(self.model.query_embed(text)))
        return {"indices": emb.indices.tolist(), "values": emb.values.tolist()}

    def embed_chunks(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        texts = [embedding_text(c) for c in chunks]
        for chunk, emb in zip(chunks, self.model.embed(texts), strict=True):
            chunk.sparse_embedding = {
                "indices": emb.indices.tolist(),
                "values": emb.values.tolist(),
            }
        return chunks
