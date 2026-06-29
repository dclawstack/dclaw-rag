from app.core.config import settings
from app.models.schemas import DocumentChunk


class Reranker:
    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(settings.reranker_model)
        self.top_k = settings.reranker_top_k

    def rerank(self, query: str, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        if not chunks:
            return chunks

        pairs = [(query, chunk.text) for chunk in chunks]
        scores = self.model.predict(pairs)

        scored = list(zip(chunks, scores, strict=True))
        scored.sort(key=lambda x: x[1], reverse=True)

        top = scored[: self.top_k]
        for chunk, score in top:
            chunk.score = float(score)

        return [chunk for chunk, _ in top]
