import json

from app.db.backend import make_kv


class CollectionStore:
    """Persistent metadata store for collections, backed by Redis.

    Every record carries a tenant_id; reads/deletes are scoped to a tenant so
    one tenant cannot see or remove another's collections.
    """

    INDEX_KEY = "collections:index"

    def __init__(self) -> None:
        self._redis = make_kv()

    def _key(self, collection_id: str) -> str:
        return f"collection:{collection_id}"

    def create(self, collection_id: str, record: dict) -> dict:
        self._redis.set(self._key(collection_id), json.dumps(record))
        self._redis.sadd(self.INDEX_KEY, collection_id)
        return record

    def get(self, collection_id: str, tenant_id: str) -> dict | None:
        raw = self._redis.get(self._key(collection_id))
        if not raw:
            return None
        record = json.loads(raw)
        return record if record.get("tenant_id") == tenant_id else None

    def list(self, tenant_id: str) -> list[dict]:
        records = []
        for collection_id in self._redis.smembers(self.INDEX_KEY):
            raw = self._redis.get(self._key(str(collection_id)))
            if raw:
                record = json.loads(raw)
                if record.get("tenant_id") == tenant_id:
                    records.append(record)
        records.sort(key=lambda r: r.get("created_at", ""))
        return records

    def delete(self, collection_id: str, tenant_id: str) -> bool:
        if self.get(collection_id, tenant_id) is None:
            return False
        self._redis.delete(self._key(collection_id))
        self._redis.srem(self.INDEX_KEY, collection_id)
        return True
