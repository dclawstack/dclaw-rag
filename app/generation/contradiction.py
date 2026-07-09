"""Contradiction flagging across retrieved sources (E4.11).

A best-effort LLM check that scans the chunks retrieved for a query and reports
factual conflicts between them (e.g. two documents stating different figures for
the same thing). Surfaced to the user as a trust signal — "your sources disagree"
— not as a hard failure. Fails open to [] so a checker hiccup never breaks the
answer.
"""

import json
from pathlib import Path

from jinja2 import Template

from app.generation.synthesis import _extract_json_object
from app.models.schemas import DocumentChunk

PROMPT_PATH = Path(__file__).parent / "prompts" / "contradiction_v1.md"


async def detect_contradictions(chunks: list[DocumentChunk], llm) -> list[str]:
    """Return short descriptions of contradictions among the chunks (or [])."""
    # Need at least two distinct sources for a contradiction to be meaningful.
    sources = {c.metadata.source for c in chunks}
    if len(chunks) < 2 or len(sources) < 2:
        return []

    snippets = [
        f"[{i}] (source: {c.metadata.source}) {c.text[:400]}"
        for i, c in enumerate(chunks[:8], 1)
    ]
    prompt = Template(PROMPT_PATH.read_text(encoding="utf-8")).render(snippets=snippets)
    messages = [
        {"role": "system", "content": "You detect factual contradictions. Respond only with JSON."},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await llm.complete(messages, temperature=0.0)
    except Exception:
        return []

    data = _extract_json_object(raw)
    items = data.get("contradictions") if isinstance(data, dict) else None
    if items is None and isinstance(data, dict):
        return []
    # Tolerate a bare JSON array too.
    if items is None:
        try:
            parsed = json.loads(raw.strip())
            items = parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, AttributeError):
            items = []
    return [str(item) for item in items][:5] if isinstance(items, list) else []
