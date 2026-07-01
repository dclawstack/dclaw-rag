#!/usr/bin/env python3
"""Logical backup/restore of the app's durable Redis data.

Redis AOF + a persistent volume (or a managed Redis with persistence) is the
primary durability mechanism; this is a portable, human-readable logical backup
on top of it — export to JSON, restore into any Redis.

Backed up: users, API keys, collections, and the document registry. Transient
data (rate-limit counters, Celery broker) is intentionally excluded.

Usage:
  python scripts/backup.py export backup.json
  python scripts/backup.py restore backup.json
"""

import argparse
import json
import sys

import redis

from app.core.config import settings

# Durable app-data key prefixes (see app/db/*_store.py). Excludes rl:* (rate
# limits) and the Celery broker (a separate Redis db).
DURABLE_PREFIXES = (
    "user:",
    "collection:",
    "collections:index",
    "doc:",
    "docs:",
    "apikey:",
)


def _durable_keys(client) -> set[str]:
    keys: set[str] = set()
    for prefix in DURABLE_PREFIXES:
        keys.update(client.scan_iter(match=f"{prefix}*"))
    return keys


def export_data(client) -> dict:
    """Snapshot durable keys as {key: {"type": ..., "value": ...}}."""
    out: dict = {}
    for key in _durable_keys(client):
        key_type = client.type(key)
        if key_type == "string":
            out[key] = {"type": "string", "value": client.get(key)}
        elif key_type == "set":
            out[key] = {"type": "set", "value": sorted(client.smembers(key))}
    return out


def import_data(client, data: dict) -> int:
    """Restore a snapshot. Returns the number of keys written."""
    for key, record in data.items():
        if record["type"] == "string":
            client.set(key, record["value"])
        elif record["type"] == "set" and record["value"]:
            client.sadd(key, *record["value"])
    return len(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup/restore durable Redis data")
    parser.add_argument("action", choices=["export", "restore"])
    parser.add_argument("path")
    parser.add_argument("--redis-url", default=settings.redis_url)
    args = parser.parse_args()

    client = redis.from_url(args.redis_url, decode_responses=True)

    if args.action == "export":
        data = export_data(client)
        with open(args.path, "w") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        print(f"Exported {len(data)} keys to {args.path}")
    else:
        with open(args.path) as fh:
            data = json.load(fh)
        n = import_data(client, data)
        print(f"Restored {n} keys from {args.path}")


if __name__ == "__main__":
    sys.exit(main())
