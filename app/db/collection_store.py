import json

import redis

from app.core.config import settings


class CollectionStore:
    """Persistent metadata store for collections, backed by Redis.

    Collections are lightweight named groupings; the documents/chunks
    themselves live in Qdrant and are associated via metadata.collection_id.
    """

    INDEX_KEY = "collections:index"

    def __init__(self) -> None:
        self._redis = redis.from_url(settings.redis_url, decode_responses=True)

    def _key(self, collection_id: str) -> str:
        return f"collection:{collection_id}"

    def create(self, collection_id: str, record: dict) -> dict:
        self._redis.set(self._key(collection_id), json.dumps(record))
        self._redis.sadd(self.INDEX_KEY, collection_id)
        return record

    def get(self, collection_id: str) -> dict | None:
        raw = self._redis.get(self._key(collection_id))
        return json.loads(raw) if raw else None

    def list(self) -> list[dict]:
        records = []
        for collection_id in self._redis.smembers(self.INDEX_KEY):
            raw = self._redis.get(self._key(collection_id))
            if raw:
                records.append(json.loads(raw))
        records.sort(key=lambda r: r.get("created_at", ""))
        return records

    def delete(self, collection_id: str) -> bool:
        existed = self._redis.delete(self._key(collection_id))
        self._redis.srem(self.INDEX_KEY, collection_id)
        return bool(existed)
