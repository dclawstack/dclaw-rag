#!/usr/bin/env python3
"""Self-contained RAG evaluation harness.

Ingests a small golden corpus into an isolated Qdrant collection, then measures:
  * hit-rate@k  — does an answerable question retrieve a chunk from its source?
  * MRR         — how high does the first correct chunk rank?
  * abstention  — do off-topic questions score below the abstain threshold?

It exercises the real retrieval stack (hybrid dense+sparse -> RRF -> rerank) but
needs no LLM: retrieval and abstention are deterministic given the models. Exits
non-zero if any metric falls below its threshold, so it can gate CI.

Usage:
  python scripts/evaluate.py [--golden eval/golden_set.json] [--top-k 10]
                             [--min-hit-rate 0.9] [--min-mrr 0.7]
                             [--min-abstain-accuracy 0.75]
"""

import argparse
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


def run(golden_path: Path, top_k: int, min_hit: float, min_mrr: float, min_abstain: float) -> int:
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
    print("=" * 60)

    failures = []
    if hit_rate < min_hit:
        failures.append(f"hit-rate {hit_rate:.1%} < {min_hit:.0%}")
    if mrr < min_mrr:
        failures.append(f"MRR {mrr:.3f} < {min_mrr:.3f}")
    if abstain_acc < min_abstain:
        failures.append(f"abstention accuracy {abstain_acc:.1%} < {min_abstain:.0%}")

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
    args = parser.parse_args()

    sys.exit(
        run(
            args.golden,
            args.top_k,
            args.min_hit_rate,
            args.min_mrr,
            args.min_abstain_accuracy,
        )
    )


if __name__ == "__main__":
    main()
