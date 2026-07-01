from app.db.query_cache import QueryCache


class _FakeRedis:
    def __init__(self):
        self.kv = {}

    def get(self, key):
        return self.kv.get(key)

    def set(self, key, value, ex=None):
        self.kv[key] = value

    def incr(self, key):
        self.kv[key] = str(int(self.kv.get(key, "0")) + 1)


def _cache(ttl=300):
    c = QueryCache.__new__(QueryCache)
    c._redis = _FakeRedis()
    c._ttl = ttl
    return c


PARAMS = {"q": "hi", "top_k": 5}


def test_set_then_get_round_trip():
    c = _cache()
    assert c.get("t1", PARAMS) is None
    c.set("t1", PARAMS, {"answer": "cached"})
    assert c.get("t1", PARAMS) == {"answer": "cached"}


def test_tenants_do_not_share_cache():
    c = _cache()
    c.set("t1", PARAMS, {"answer": "for-t1"})
    assert c.get("t2", PARAMS) is None


def test_version_bump_invalidates():
    c = _cache()
    c.set("t1", PARAMS, {"answer": "old"})
    assert c.get("t1", PARAMS) == {"answer": "old"}
    c.bump_version("t1")
    assert c.get("t1", PARAMS) is None  # previous version's key is unreachable


def test_ttl_zero_disables_cache():
    c = _cache(ttl=0)
    c.set("t1", PARAMS, {"answer": "x"})
    assert c.get("t1", PARAMS) is None
