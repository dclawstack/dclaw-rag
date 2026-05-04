from app.core.config import settings
from app.models.schemas import DocumentChunk


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
        texts = [c.text for c in chunks]
        embeddings = self.embed(texts)
        for chunk, emb in zip(chunks, embeddings):
            chunk.embedding = emb
        return chunks
