from app.db.refresh_token_store import RefreshTokenStore


class _FakeRedis:
    def __init__(self):
        self.kv = {}
        self.sets = {}

    def set(self, key, value, ex=None):
        self.kv[key] = value

    def get(self, key):
        return self.kv.get(key)

    def delete(self, key):
        self.kv.pop(key, None)
        self.sets.pop(key, None)

    def sadd(self, key, *values):
        self.sets.setdefault(key, set()).update(values)

    def srem(self, key, *values):
        self.sets.get(key, set()).difference_update(values)

    def smembers(self, key):
        return set(self.sets.get(key, set()))


def _store():
    s = RefreshTokenStore.__new__(RefreshTokenStore)
    s._redis = _FakeRedis()
    s._ttl = 100
    return s


def test_issue_and_validate():
    s = _store()
    jti = s.issue("user-1")
    assert s.is_valid(jti, "user-1") is True
    assert s.is_valid(jti, "someone-else") is False
    assert s.is_valid("made-up-jti", "user-1") is False


def test_revoke_single_session():
    s = _store()
    jti = s.issue("user-1")
    s.revoke(jti, "user-1")
    assert s.is_valid(jti, "user-1") is False


def test_revoke_all_sessions():
    s = _store()
    a, b, c = s.issue("user-1"), s.issue("user-1"), s.issue("user-2")
    revoked = s.revoke_all("user-1")
    assert revoked == 2
    assert s.is_valid(a, "user-1") is False
    assert s.is_valid(b, "user-1") is False
    assert s.is_valid(c, "user-2") is True  # other user's session untouched
