#!/usr/bin/env python3
"""Self-contained RAG evaluation harness.

Ingests a small golden corpus into an isolated Qdrant collection, then measures:
  * hit-rate@k  — does an answerable question retrieve a chunk from its source?
  * MRR         — how high does the first correct chunk rank?
  * abstention  — do off-topic questions score below the abstain threshold?

  * answer quality — (optional) run the full RAG pipeline and have an LLM judge
    score each answer against a reference. Runs only when the configured LLM
    provider is reachable; otherwise it is skipped (not failed), so CI without a
    key still passes on the deterministic metrics above.

The retrieval/abstention metrics need no LLM and are deterministic given the
models. Exits non-zero if any computed metric falls below its threshold.

Usage:
  python scripts/evaluate.py [--golden eval/golden_set.json] [--top-k 10]
                             [--min-hit-rate 0.9] [--min-mrr 0.7]
                             [--min-abstain-accuracy 0.75]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.core.config import settings

DEFAULT_GOLDEN = Path(__file__).resolve().parent.parent / "eval" / "golden_set.json"
EVAL_COLLECTION = "eval_golden"
EVAL_TENANT = "eval"


def _ingest_corpus(corpus: list[dict]) -> None:
    """Recreate the eval collection and ingest the corpus into it."""
    from qdrant_client import QdrantClient

    from app.ingestion.pipeline import IngestionPipeline
    from app.models.schemas import IngestRequest

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    if client.collection_exists(EVAL_COLLECTION):
        client.delete_collection(EVAL_COLLECTION)

    pipeline = IngestionPipeline()  # constructs against EVAL_COLLECTION, ensures it exists
    for doc in corpus:
        pipeline.ingest_text(
            doc["text"],
            IngestRequest(source=doc["source"], title=doc.get("title"), tenant_id=EVAL_TENANT),
        )


def _llm_available() -> bool:
    """True if the configured LLM provider can be reached (so answer-quality
    grading can run). False -> grading is skipped, not failed."""
    keyed = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "openrouter": settings.openrouter_api_key,
    }
    if settings.llm_provider in keyed:
        return bool(keyed[settings.llm_provider])
    if settings.llm_provider == "ollama":
        import httpx

        try:
            httpx.get(settings.ollama_url, timeout=2.0)
            return True
        except Exception:
            return False
    return False


async def _grade_answers(data: dict, searcher, top_k: int) -> list[float]:
    """For each answerable question, run the real RAG pipeline and have an LLM
    judge score the answer against the reference (0..1)."""
    from app.generation.llm_gateway import get_llm_gateway
    from app.generation.synthesis import _extract_json_object, parse_answer, render_rag_prompt

    llm = get_llm_gateway()
    scores: list[float] = []
    for item in data["answerable"]:
        chunks = searcher.search(item["question"], top_k=top_k)
        raw = await llm.complete(
            [
                {"role": "system", "content": "You are a helpful RAG assistant."},
                {"role": "user", "content": render_rag_prompt(chunks, item["question"])},
            ]
        )
        answer, _, _ = parse_answer(raw)
        judge_prompt = (
            "Score how well the CANDIDATE conveys the key facts of the REFERENCE "
            "answer to the QUESTION, from 0.0 to 1.0. Respond with ONLY JSON: "
            '{"score": <float 0-1>, "reason": "<short>"}.\n\n'
            f"QUESTION: {item['question']}\n"
            f"REFERENCE: {item['expected_answer']}\n"
            f"CANDIDATE: {answer}"
        )
        verdict_raw = await llm.complete([{"role": "user", "content": judge_prompt}])
        verdict = _extract_json_object(verdict_raw)
        try:
            scores.append(max(0.0, min(1.0, float((verdict or {}).get("score", 0.0)))))
        except (TypeError, ValueError):
            scores.append(0.0)
    return scores


def _append_history(history_path: Path, record: dict) -> None:
    """Append one JSON line of eval metrics so quality can be tracked over time."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def run(
    golden_path: Path,
    top_k: int,
    min_hit: float,
    min_mrr: float,
    min_abstain: float,
    min_answer_score: float,
    history_path: Path | None = None,
) -> int:
    data = json.loads(golden_path.read_text())

    # Isolate eval data from any real collection BEFORE stores are constructed.
    settings.qdrant_collection = EVAL_COLLECTION

    _ingest_corpus(data["corpus"])

    from app.retrieval.search import Searcher

    searcher = Searcher()

    # --- answerable: hit-rate@k and MRR by expected source ---
    hits = 0
    reciprocal_ranks = []
    for item in data["answerable"]:
        chunks = searcher.search(item["question"], top_k=top_k)
        sources = [c.metadata.source for c in chunks]
        expected = item["expected_source"]
        rank = next((i for i, s in enumerate(sources) if s == expected), None)
        if rank is not None:
            hits += 1
            reciprocal_ranks.append(1.0 / (rank + 1))
        else:
            reciprocal_ranks.append(0.0)

    n_ans = len(data["answerable"])
    hit_rate = hits / n_ans if n_ans else 0.0
    mrr = sum(reciprocal_ranks) / n_ans if n_ans else 0.0

    # --- unanswerable: should abstain (top rerank score below threshold) ---
    correct_abstentions = 0
    for item in data["unanswerable"]:
        chunks = searcher.search(item["question"], top_k=top_k)
        top_score = chunks[0].score if chunks and chunks[0].score is not None else 0.0
        if top_score < settings.abstain_threshold:
            correct_abstentions += 1

    n_unans = len(data["unanswerable"])
    abstain_acc = correct_abstentions / n_unans if n_unans else 1.0

    # --- answer quality (LLM-graded; skipped when no provider key is available) ---
    answer_score: float | None = None
    if _llm_available():
        graded = asyncio.run(_grade_answers(data, searcher, top_k))
        answer_score = sum(graded) / len(graded) if graded else 0.0

    # --- report ---
    print("=" * 60)
    print(f"RAG evaluation  (top_k={top_k}, abstain_threshold={settings.abstain_threshold})")
    print("=" * 60)
    print(f"  Hit-rate@{top_k:<3}      {hit_rate:6.1%}  ({hits}/{n_ans})        min {min_hit:.0%}")
    print(f"  MRR              {mrr:6.3f}                  min {min_mrr:.3f}")
    print(
        f"  Abstention acc.  {abstain_acc:6.1%}  "
        f"({correct_abstentions}/{n_unans})        min {min_abstain:.0%}"
    )
    if answer_score is None:
        print("  Answer quality   skipped  (no LLM provider key)")
    else:
        print(f"  Answer quality   {answer_score:6.3f}                  min {min_answer_score:.3f}")
    print("=" * 60)

    failures = []
    if hit_rate < min_hit:
        failures.append(f"hit-rate {hit_rate:.1%} < {min_hit:.0%}")
    if mrr < min_mrr:
        failures.append(f"MRR {mrr:.3f} < {min_mrr:.3f}")
    if abstain_acc < min_abstain:
        failures.append(f"abstention accuracy {abstain_acc:.1%} < {min_abstain:.0%}")
    if answer_score is not None and answer_score < min_answer_score:
        failures.append(f"answer quality {answer_score:.3f} < {min_answer_score:.3f}")

    if history_path is not None:
        from datetime import UTC, datetime

        _append_history(
            history_path,
            {
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "dataset": golden_path.name,
                "dataset_version": data.get("version"),
                "top_k": top_k,
                "hit_rate": round(hit_rate, 4),
                "mrr": round(mrr, 4),
                "abstain_accuracy": round(abstain_acc, 4),
                "answer_score": round(answer_score, 4) if answer_score is not None else None,
                "passed": not failures,
            },
        )
        print(f"  (appended metrics to {history_path})")

    if failures:
        print("FAIL: " + "; ".join(failures))
        return 1
    print("PASS: all metrics meet thresholds")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Self-contained RAG evaluation")
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--min-hit-rate", type=float, default=0.9)
    parser.add_argument("--min-mrr", type=float, default=0.7)
    parser.add_argument("--min-abstain-accuracy", type=float, default=0.75)
    parser.add_argument("--min-answer-score", type=float, default=0.6)
    parser.add_argument(
        "--history",
        type=Path,
        default=None,
        help="Append this run's metrics as a JSON line here (track quality over time)",
    )
    args = parser.parse_args()

    sys.exit(
        run(
            args.golden,
            args.top_k,
            args.min_hit_rate,
            args.min_mrr,
            args.min_abstain_accuracy,
            args.min_answer_score,
            history_path=args.history,
        )
    )


if __name__ == "__main__":
    main()
