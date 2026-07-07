import json

from app.db.backend import make_kv


class DocumentStore:
    """Registry of ingested documents and their processing status, in Redis.

    This is the source of truth for *documents* (Qdrant holds their chunks). It
    tracks status across async ingestion (pending -> processing -> ready/failed)
    and supports O(1) per-tenant / per-collection counts. Every record carries a
    tenant_id; reads are tenant-scoped.
    """

    def __init__(self) -> None:
        self._redis = make_kv()

    def _key(self, doc_id: str) -> str:
        return f"doc:{doc_id}"

    def _tenant_index(self, tenant_id: str) -> str:
        return f"docs:t:{tenant_id}"

    def _collection_index(self, collection_id: str) -> str:
        return f"docs:c:{collection_id}"

    def _checksum_key(self, tenant_id: str, checksum: str) -> str:
        return f"docs:cs:{tenant_id}:{checksum}"

    def create(self, record: dict) -> dict:
        doc_id = record["id"]
        self._redis.set(self._key(doc_id), json.dumps(record))
        self._redis.sadd(self._tenant_index(record["tenant_id"]), doc_id)
        if record.get("collection_id"):
            self._redis.sadd(self._collection_index(record["collection_id"]), doc_id)
        if record.get("checksum"):
            self._redis.set(self._checksum_key(record["tenant_id"], record["checksum"]), doc_id)
        return record

    def get(self, doc_id: str, tenant_id: str) -> dict | None:
        raw = self._redis.get(self._key(doc_id))
        if not raw:
            return None
        record = json.loads(raw)
        return record if record.get("tenant_id") == tenant_id else None

    def set_status(self, doc_id: str, status: str, **fields: object) -> None:
        """Update a document's status (and optional fields like chunk_count /
        error). No tenant check — called by the worker, which owns the doc_id."""
        raw = self._redis.get(self._key(doc_id))
        if not raw:
            return
        record = json.loads(raw)
        record["status"] = status
        record.update(fields)
        self._redis.set(self._key(doc_id), json.dumps(record))

    def find_by_checksum(self, tenant_id: str, checksum: str) -> dict | None:
        doc_id = self._redis.get(self._checksum_key(tenant_id, checksum))
        return self.get(str(doc_id), tenant_id) if doc_id else None

    def _index_for(self, tenant_id: str, collection_id: str | None) -> str:
        return (
            self._collection_index(collection_id)
            if collection_id
            else self._tenant_index(tenant_id)
        )

    def count(self, tenant_id: str, collection_id: str | None = None) -> int:
        return self._redis.scard(self._index_for(tenant_id, collection_id))

    def list(
        self,
        tenant_id: str,
        collection_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        records = []
        for doc_id in self._redis.smembers(self._index_for(tenant_id, collection_id)):
            raw = self._redis.get(self._key(str(doc_id)))
            if raw:
                record = json.loads(raw)
                if record.get("tenant_id") == tenant_id:
                    records.append(record)
        # newest first, then page
        records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return records[offset : offset + limit]
