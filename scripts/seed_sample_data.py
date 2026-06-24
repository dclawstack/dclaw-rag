#!/usr/bin/env python3
"""Seed the RAG knowledge base with sample documents for manual testing.

Talks to a *running* backend over HTTP (start it first — see
docs/guides/manual-testing.md). Uses only the standard library.

Usage:
    python scripts/seed_sample_data.py
    python scripts/seed_sample_data.py --api-url http://localhost:8090
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

COLLECTION = {
    "name": "Sample Knowledge Base",
    "description": "Seeded sample documents for manual testing",
}

# Cross-referencing docs so multi-step (agentic) queries have something to do.
DOCUMENTS = [
    {
        "title": "Acme Q1 2026 Financials",
        "source": "seed/finance",
        "text": (
            "Acme Corporation reported Q1 2026 revenue of $3.2 million, with a gross "
            "margin of 61%. Net new customers in the quarter totaled 140. "
            "Operating expenses were $2.1 million."
        ),
    },
    {
        "title": "Acme Q3 2026 Financials",
        "source": "seed/finance",
        "text": (
            "Acme Corporation reported Q3 2026 revenue of $5.0 million, up sharply from "
            "earlier in the year. Gross margin improved to 64%. The company added 320 "
            "net new customers and reached cash-flow breakeven for the first time."
        ),
    },
    {
        "title": "Product Return Policy",
        "source": "seed/support",
        "text": (
            "Customers may return any Acme product within 30 days of delivery for a full "
            "refund. Items must be unused and in original packaging. Refunds are issued to "
            "the original payment method within 5 business days of receiving the return."
        ),
    },
    {
        "title": "New Employee Onboarding",
        "source": "seed/hr",
        "text": (
            "On your first day at Acme, collect your laptop from IT, enroll in SSO and the "
            "VPN, and complete the security training module. Your manager will schedule a "
            "first-week check-in. Benefits enrollment must be completed within 30 days."
        ),
    },
    {
        "title": "Data Handling Overview",
        "source": "seed/security",
        "text": (
            "Acme classifies data as public, internal, or confidential. Confidential data "
            "must be encrypted at rest and in transit. Access is granted on a least-privilege "
            "basis and reviewed quarterly. PII must never be sent to third-party services "
            "without an approved data-processing agreement."
        ),
    },
]


def _request(url: str, payload: dict | None = None, method: str = "GET") -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def main(api_url: str) -> None:
    api_url = api_url.rstrip("/")
    base = f"{api_url}/api/v1/rag"

    try:
        health = _request(f"{api_url}/health")
    except urllib.error.URLError as exc:
        print(f"error: backend not reachable at {api_url} ({exc}).")
        print("Start it first: uvicorn app.api.main:app --port 8090  (or docker compose up)")
        sys.exit(1)
    print(f"backend ok: {health}")

    collection = _request(f"{base}/collections", COLLECTION, method="POST")
    collection_id = collection["id"]
    print(f"created collection '{collection['name']}' ({collection_id})")

    print("ingesting sample documents (first one may be slow — models download on first use)...")
    for doc in DOCUMENTS:
        try:
            result = _request(
                f"{base}/documents/text",
                {
                    "text": doc["text"],
                    "metadata": {
                        "source": doc["source"],
                        "title": doc["title"],
                        "collection_id": collection_id,
                    },
                },
                method="POST",
            )
        except urllib.error.HTTPError as exc:
            print(f"  failed '{doc['title']}': {exc.code} {exc.read().decode(errors='ignore')}")
            continue
        print(f"  ingested '{doc['title']}' -> {result['chunks_inserted']} chunk(s)")

    print("\nDone. Try these (needs an LLM key for answers):")
    print(f"  curl -X POST {base}/query -H 'Content-Type: application/json' \\")
    print('    -d \'{"question":"What was Acme\\u2019s Q3 2026 revenue?","top_k":5}\'')
    print(f"  curl -X POST {base}/agent -H 'Content-Type: application/json' \\")
    print('    -d \'{"question":"How did Acme revenue change from Q1 to Q3 2026?","max_steps":3}\'')
    print("Or open the UI at http://localhost:3003 and select the 'Sample Knowledge Base' collection.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed sample data for manual testing")
    parser.add_argument(
        "--api-url",
        default="http://localhost:8090",
        help="Base URL of the running backend (default: http://localhost:8090)",
    )
    args = parser.parse_args()
    main(args.api_url)
