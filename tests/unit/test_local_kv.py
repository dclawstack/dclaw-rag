"""LocalKV semantics the store tests don't reach: expiry, counters, setnx —
each must match redis-py with decode_responses=True."""

import pytest

from app.db.backend import LocalKV


@pytest.fixture
def kv(tmp_path):
    return LocalKV(str(tmp_path / "kv.sqlite3"))


def test_get_set_roundtrip_returns_strings(kv):
    assert kv.get("k") is None
    kv.set("k", 42)
    assert kv.get("k") == "42"


def test_set_with_ex_expires(kv, monkeypatch):
    import app.db.backend as backend

    now = 1000.0
    monkeypatch.setattr(backend.time, "time", lambda: now)
    kv.set("k", "v", ex=60)
    assert kv.get("k") == "v"
    assert kv.exists("k") == 1

    now = 1061.0
    assert kv.get("k") is None
    assert kv.exists("k") == 0


def test_plain_set_clears_ttl(kv, monkeypatch):
    import app.db.backend as backend

    now = 1000.0
    monkeypatch.setattr(backend.time, "time", lambda: now)
    kv.set("k", "v", ex=60)
    kv.set("k", "v2")  # redis SET without ex drops the TTL
    now = 2000.0
    assert kv.get("k") == "v2"


def test_expire_sets_ttl_on_existing_key_only(kv, monkeypatch):
    import app.db.backend as backend

    now = 1000.0
    monkeypatch.setattr(backend.time, "time", lambda: now)
    assert kv.expire("missing", 60) is False
    kv.set("k", "v")
    assert kv.expire("k", 60) is True
    now = 1061.0
    assert kv.get("k") is None


def test_setnx_only_sets_when_absent(kv):
    assert kv.setnx("k", "first") is True
    assert kv.setnx("k", "second") is False
    assert kv.get("k") == "first"


def test_setnx_treats_expired_key_as_absent(kv, monkeypatch):
    import app.db.backend as backend

    now = 1000.0
    monkeypatch.setattr(backend.time, "time", lambda: now)
    kv.set("k", "old", ex=10)
    now = 1011.0
    assert kv.setnx("k", "new") is True
    assert kv.get("k") == "new"


def test_incr_family(kv):
    assert kv.incr("n") == 1
    assert kv.incr("n") == 2
    assert kv.incrby("n", 10) == 12
    assert kv.incrbyfloat("f", 0.5) == 0.5
    assert kv.incrbyfloat("f", 0.25) == 0.75
    assert kv.get("n") == "12"


def test_sets_and_delete_span_both_tables(kv):
    kv.sadd("s", "a", "b")
    assert kv.sadd("s", "b") == 0  # already present
    assert kv.smembers("s") == {"a", "b"}
    assert kv.scard("s") == 2
    assert kv.srem("s", "a") == 1
    assert kv.smembers("s") == {"b"}

    kv.set("k", "v")
    assert kv.delete("k") == 1
    assert kv.delete("s") == 1  # DEL works on set keys too
    assert kv.scard("s") == 0
    assert kv.delete("missing") == 0


def test_ping(kv):
    assert kv.ping() is True


def test_persists_across_instances(tmp_path):
    path = str(tmp_path / "kv.sqlite3")
    LocalKV(path).set("k", "v")
    assert LocalKV(path).get("k") == "v"
