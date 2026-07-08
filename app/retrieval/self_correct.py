"""Self-correcting retrieval.

When a first search returns only weakly-relevant chunks (top reranked score below
`self_correct_threshold`), reformulate the query once with the LLM and search
again, keeping whichever attempt retrieved the stronger evidence. This rescues
answerable questions that were merely phrased differently from the source before
the query route decides to abstain — without an extra round-trip on the common
case where the first search is already strong.
"""

import structlog

from app.core.config import settings
from app.generation.llm_gateway import LLMGateway
from app.models.schemas import DocumentChunk
from app.retrieval.search import Searcher

logger = structlog.get_logger(__name__)

_REFORMULATE_SYSTEM = "You rewrite search queries to improve document retrieval."
_REFORMULATE_TEMPLATE = (
    "The search below returned weak results. Rewrite it as a single, more "
    "effective retrieval query: expand abbreviations, add likely synonyms and "
    "concrete terms a relevant document would use, and drop conversational "
    "filler. Return ONLY the rewritten query, no quotes or preamble.\n\n"
    "Original query: {question}"
)


def _top_score(chunks: list[DocumentChunk]) -> float:
    return max((c.score or 0.0 for c in chunks), default=float("-inf"))


async def _reformulate(llm: LLMGateway, question: str) -> str | None:
    messages = [
        {"role": "system", "content": _REFORMULATE_SYSTEM},
        {"role": "user", "content": _REFORMULATE_TEMPLATE.format(question=question)},
    ]
    try:
        raw = await llm.complete(messages, temperature=0.0)
    except Exception:
        return None  # reformulation is best-effort; never break the query
    reformulated = raw.strip().strip('"').splitlines()[0].strip() if raw.strip() else ""
    if not reformulated or reformulated.lower() == question.strip().lower():
        return None
    return reformulated


async def search_self_correcting(
    searcher: Searcher,
    llm: LLMGateway,
    question: str,
    top_k: int,
    filters: dict | None,
) -> tuple[list[DocumentChunk], str | None]:
    """Search; if weak, reformulate once and re-search, keeping the better set.

    Returns (chunks, reformulated_query_or_None). Falls back to the original
    results whenever reformulation is disabled, fails, or doesn't help.
    """
    chunks = searcher.search(question, top_k=top_k, filters=filters)
    if not settings.self_correct_retrieval:
        return chunks, None
    if _top_score(chunks) >= settings.self_correct_threshold:
        return chunks, None

    reformulated = await _reformulate(llm, question)
    if reformulated is None:
        return chunks, None

    retry = searcher.search(reformulated, top_k=top_k, filters=filters)
    if _top_score(retry) > _top_score(chunks):
        logger.info(
            "self_correct_retrieval_improved",
            original_top=round(_top_score(chunks), 3),
            retry_top=round(_top_score(retry), 3),
        )
        return retry, reformulated
    return chunks, None
