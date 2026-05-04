#!/usr/bin/env python3
"""Evaluate retrieval hit-rate on a benchmark dataset."""

import argparse
import json
from pathlib import Path

from app.retrieval.search import Searcher


def main(benchmark_path: Path, top_k: int) -> None:
    searcher = Searcher()
    data = json.loads(benchmark_path.read_text())

    hits = 0
    total = 0

    for item in data:
        question = item["question"]
        golden_ids = set(item["golden_chunk_ids"])

        chunks = searcher.search(question, top_k=top_k)
        retrieved_ids = {str(c.id) for c in chunks}

        if golden_ids & retrieved_ids:
            hits += 1
        total += 1

    print(f"Hit Rate @ {top_k}: {hits}/{total} = {hits / total:.2%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate retrieval")
    parser.add_argument("benchmark", type=Path, help="Path to benchmark JSON")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    main(args.benchmark, args.top_k)
