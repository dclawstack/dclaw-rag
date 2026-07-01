"""Unit tests for the Redis-backed stores, driven by a fake Redis so they run
without a real server (and exercise the store logic the integration tests skip
by using fakes)."""

from app.db.collection_store import CollectionStore
from app.db.document_store import DocumentStore
from app.db.user_store import UserStore


class FakeRedis:
    def __init__(self):
        self.kv = {}
        self.sets = {}

    def get(self, key):
        return self.kv.get(key)

    def set(self, key, value, ex=None):
        self.kv[key] = value

    def setnx(self, key, value):
        if key in self.kv:
            return False
        self.kv[key] = value
        return True

    def delete(self, key):
        self.kv.pop(key, None)
        self.sets.pop(key, None)

    def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    def srem(self, key, *values):
        self.sets.get(key, set()).difference_update(values)

    def smembers(self, key):
        return set(self.sets.get(key, set()))

    def scard(self, key):
        return len(self.sets.get(key, set()))


def _make(cls):
    store = cls.__new__(cls)
    store._redis = FakeRedis()
    return store


# --- CollectionStore ---


def test_collection_store_tenant_scoping():
    s = _make(CollectionStore)
    s.create("c1", {"id": "c1", "tenant_id": "A", "created_at": "1"})
    s.create("c2", {"id": "c2", "tenant_id": "B", "created_at": "2"})

    assert s.get("c1", "A")["id"] == "c1"
    assert s.get("c1", "B") is None  # wrong tenant
    assert [c["id"] for c in s.list("A")] == ["c1"]
    assert s.list("B")[0]["id"] == "c2"


def test_collection_store_delete_is_tenant_scoped():
    s = _make(CollectionStore)
    s.create("c1", {"id": "c1", "tenant_id": "A", "created_at": "1"})
    assert s.delete("c1", "B") is False  # other tenant can't delete
    assert s.delete("c1", "A") is True
    assert s.get("c1", "A") is None
    assert s.delete("c1", "A") is False  # already gone


# --- DocumentStore ---


def _doc(doc_id, tenant, collection=None, checksum=None, created="1"):
    return {
        "id": doc_id,
        "tenant_id": tenant,
        "collection_id": collection,
        "checksum": checksum,
        "status": "pending",
        "created_at": created,
    }


def test_document_store_counts_and_tenant_scope():
    s = _make(DocumentStore)
    s.create(_doc("d1", "A", collection="c1"))
    s.create(_doc("d2", "A", collection="c1"))
    s.create(_doc("d3", "B"))

    assert s.count("A") == 2
    assert s.count("A", "c1") == 2
    assert s.count("B") == 1
    assert s.get("d1", "A")["id"] == "d1"
    assert s.get("d1", "B") is None  # wrong tenant


def test_document_store_status_and_checksum():
    s = _make(DocumentStore)
    s.create(_doc("d1", "A", checksum="abc"))

    assert s.find_by_checksum("A", "abc")["id"] == "d1"
    assert s.find_by_checksum("B", "abc") is None

    s.set_status("d1", "ready", chunk_count=7)
    rec = s.get("d1", "A")
    assert rec["status"] == "ready" and rec["chunk_count"] == 7


def test_document_store_list_pagination_newest_first():
    s = _make(DocumentStore)
    for i in range(5):
        s.create(_doc(f"d{i}", "A", created=str(i)))
    page = s.list("A", limit=2, offset=0)
    assert [d["id"] for d in page] == ["d4", "d3"]  # newest first
    assert [d["id"] for d in s.list("A", limit=2, offset=2)] == ["d2", "d1"]


# --- UserStore ---


def test_user_store_create_and_lookup():
    s = _make(UserStore)
    rec = {"id": "u1", "email": "A@B.com", "tenant_id": "t1"}
    s.create(rec)

    assert s.get_by_id("u1")["email"] == "A@B.com"
    assert s.get_by_email("a@b.com")["id"] == "u1"  # case-insensitive
    assert s.get_by_email("missing@x.com") is None


def test_user_store_rejects_duplicate_email():
    s = _make(UserStore)
    s.create({"id": "u1", "email": "dup@x.com", "tenant_id": "t1"})
    try:
        s.create({"id": "u2", "email": "dup@x.com", "tenant_id": "t2"})
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
