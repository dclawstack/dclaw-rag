"""Backend selection for the KV stores and Qdrant.

In server mode (the default) the stores talk to real Redis and an external
Qdrant, exactly as before. In local mode (`APP_MODE=local`) `make_kv()` returns
a SQLite-backed `LocalKV` shim and `get_qdrant_client()` an embedded
(file-based) Qdrant — zero external services.

Both local backends are process-wide singletons: SQLite writes are serialized
through one connection, and an embedded Qdrant *locks its directory*, so there
must be exactly ONE QdrantClient(path=...) per process.
"""

import builtins
import sqlite3
import threading
import time
from typing import TYPE_CHECKING

import redis

from app.core.config import settings

if TYPE_CHECKING:
    from qdrant_client import QdrantClient


class LocalKV:
    """SQLite-backed shim over the Redis subset the stores use.

    Mirrors redis-py with decode_responses=True: values in and out are strings,
    counters return numbers, expired keys read as absent. Safe to share across
    threads (one connection, one lock — WAL keeps readers cheap).
    """

    def __init__(self, path: str) -> None:
        import pathlib

        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS kv ("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL, expires_at REAL)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS set_members ("
                "key TEXT NOT NULL, member TEXT NOT NULL, PRIMARY KEY (key, member))"
            )

    # --- string keys ---

    def get(self, key: str) -> str | None:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT value, expires_at FROM kv WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            value, expires_at = row
            if expires_at is not None and expires_at <= time.time():
                self._conn.execute("DELETE FROM kv WHERE key = ?", (key,))
                return None
            return value

    def set(self, key: str, value: object, ex: int | None = None) -> bool:
        # Like redis SET: an existing TTL is discarded unless ex is given.
        expires_at = time.time() + ex if ex else None
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO kv (key, value, expires_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "expires_at = excluded.expires_at",
                (key, str(value), expires_at),
            )
        return True

    def setnx(self, key: str, value: object) -> bool:
        with self._lock, self._conn:
            if self.get(key) is not None:
                return False
            self._conn.execute(
                "INSERT OR REPLACE INTO kv (key, value, expires_at) VALUES (?, ?, NULL)",
                (key, str(value)),
            )
            return True

    def delete(self, *keys: str) -> int:
        count = 0
        with self._lock, self._conn:
            for key in keys:
                if (
                    self._conn.execute("DELETE FROM kv WHERE key = ?", (key,)).rowcount
                    or self._conn.execute(
                        "DELETE FROM set_members WHERE key = ?", (key,)
                    ).rowcount
                ):
                    count += 1
        return count

    def exists(self, *keys: str) -> int:
        return sum(1 for key in keys if self.get(key) is not None)

    def expire(self, key: str, seconds: int) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "UPDATE kv SET expires_at = ? WHERE key = ?", (time.time() + seconds, key)
            )
            return cursor.rowcount > 0

    # --- counters ---

    def incr(self, key: str, amount: int = 1) -> int:
        return self.incrby(key, amount)

    def incrby(self, key: str, amount: int = 1) -> int:
        with self._lock, self._conn:
            value = int(self.get(key) or 0) + amount
            self.set(key, value)
            return value

    def incrbyfloat(self, key: str, amount: float) -> float:
        with self._lock, self._conn:
            value = float(self.get(key) or 0.0) + amount
            self.set(key, value)
            return value

    # --- sets ---

    def sadd(self, key: str, *values: object) -> int:
        added = 0
        with self._lock, self._conn:
            for value in values:
                cursor = self._conn.execute(
                    "INSERT OR IGNORE INTO set_members (key, member) VALUES (?, ?)",
                    (key, str(value)),
                )
                added += cursor.rowcount
        return added

    def srem(self, key: str, *values: object) -> int:
        removed = 0
        with self._lock, self._conn:
            for value in values:
                cursor = self._conn.execute(
                    "DELETE FROM set_members WHERE key = ? AND member = ?", (key, str(value))
                )
                removed += cursor.rowcount
        return removed

    # builtins.set: inside the class body a bare `set` is the method above.
    def smembers(self, key: str) -> builtins.set[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT member FROM set_members WHERE key = ?", (key,)
            ).fetchall()
        return {row[0] for row in rows}

    def scard(self, key: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM set_members WHERE key = ?", (key,)
            ).fetchone()
        return row[0]

    # --- health ---

    def ping(self) -> bool:
        with self._lock:
            self._conn.execute("SELECT 1")
        return True


KVClient = redis.Redis | LocalKV

_local_kv: LocalKV | None = None
_qdrant_client: "QdrantClient | None" = None
_backend_lock = threading.Lock()


def make_kv() -> KVClient:
    """The stores' KV client: real Redis, or the shared LocalKV in local mode."""
    if settings.app_mode == "local":
        global _local_kv
        with _backend_lock:
            if _local_kv is None:
                _local_kv = LocalKV(str(settings.sqlite_path))
            return _local_kv
    return redis.from_url(settings.redis_url, decode_responses=True)


def get_qdrant_client() -> "QdrantClient":
    """Process-wide Qdrant client. Embedded (path=) in local mode — the data
    dir is lock-owned by this single instance; never construct another."""
    global _qdrant_client
    with _backend_lock:
        if _qdrant_client is None:
            from qdrant_client import QdrantClient

            if settings.app_mode == "local":
                settings.qdrant_path.mkdir(parents=True, exist_ok=True)
                _qdrant_client = QdrantClient(path=str(settings.qdrant_path))
            else:
                _qdrant_client = QdrantClient(
                    url=settings.qdrant_url, api_key=settings.qdrant_api_key or None
                )
        return _qdrant_client


def reset_backends_for_tests() -> None:
    """Drop the cached singletons so tests can repoint settings at a tmp dir."""
    global _local_kv, _qdrant_client
    with _backend_lock:
        if _qdrant_client is not None:
            _qdrant_client.close()
        _local_kv = None
        _qdrant_client = None
