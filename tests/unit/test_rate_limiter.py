from app.db.rate_limiter import RateLimiter


class _FakeRedis:
    """Minimal INCR/EXPIRE store for the fixed-window counter."""

    def __init__(self):
        self.counters = {}

    def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def expire(self, key, seconds):
        pass


def _limiter(limit):
    rl = RateLimiter.__new__(RateLimiter)  # bypass Redis connection in __init__
    rl._redis = _FakeRedis()
    rl.limit = limit
    return rl


def test_allows_up_to_limit_then_blocks():
    rl = _limiter(limit=3)
    results = [rl.check("acme")[0] for _ in range(5)]
    assert results == [True, True, True, False, False]


def test_block_reports_positive_retry_after():
    rl = _limiter(limit=1)
    assert rl.check("acme") == (True, 0)
    allowed, retry_after = rl.check("acme")
    assert allowed is False
    assert 0 < retry_after <= RateLimiter.WINDOW_SECONDS


def test_zero_limit_disables_limiting():
    rl = _limiter(limit=0)
    assert all(rl.check("acme")[0] for _ in range(100))


def test_tenants_are_isolated():
    rl = _limiter(limit=1)
    assert rl.check("a")[0] is True
    assert rl.check("b")[0] is True  # separate counter
    assert rl.check("a")[0] is False
