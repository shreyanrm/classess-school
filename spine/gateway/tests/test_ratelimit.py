"""Rate limiter: triggers and resets. No network/DB; deterministic clock."""

import pytest

from app.ratelimit import (
    Algorithm,
    InMemoryRateLimitStore,
    RateLimiter,
    RateLimitExceeded,
    RateLimitRule,
    RedisRateLimitStore,
    enforce,
)


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def test_token_bucket_triggers_after_limit():
    clock = FakeClock()
    rule = RateLimitRule(limit=3, window_seconds=60, algorithm=Algorithm.TOKEN_BUCKET)
    limiter = RateLimiter(default_rule=rule, clock=clock)

    for _ in range(3):
        assert limiter.check("uuid-a", "learning.read").allowed is True

    denied = limiter.check("uuid-a", "learning.read")
    assert denied.allowed is False
    assert denied.remaining == 0
    assert denied.retry_after > 0


def test_token_bucket_refills_over_time():
    clock = FakeClock()
    rule = RateLimitRule(limit=2, window_seconds=2, algorithm=Algorithm.TOKEN_BUCKET)
    limiter = RateLimiter(default_rule=rule, clock=clock)

    assert limiter.check("p", "r").allowed
    assert limiter.check("p", "r").allowed
    assert limiter.check("p", "r").allowed is False

    # one token per second refill; advance enough for one token.
    clock.advance(1.0)
    assert limiter.check("p", "r").allowed is True
    # immediately exhausted again
    assert limiter.check("p", "r").allowed is False


def test_fixed_window_triggers_and_resets_on_boundary():
    clock = FakeClock(t=100.0)
    rule = RateLimitRule(limit=2, window_seconds=10, algorithm=Algorithm.FIXED_WINDOW)
    limiter = RateLimiter(default_rule=rule, clock=clock)

    assert limiter.check("p", "r").allowed
    assert limiter.check("p", "r").allowed
    assert limiter.check("p", "r").allowed is False

    # cross the window boundary (window = [100,110); jump to 110).
    clock.t = 110.0
    assert limiter.check("p", "r").allowed is True


def test_per_principal_isolation():
    clock = FakeClock()
    rule = RateLimitRule(limit=1, window_seconds=60)
    limiter = RateLimiter(default_rule=rule, clock=clock)
    assert limiter.check("a", "r").allowed
    assert limiter.check("a", "r").allowed is False
    # different principal has its own bucket.
    assert limiter.check("b", "r").allowed is True


def test_per_route_isolation_and_override():
    clock = FakeClock()
    default = RateLimitRule(limit=5, window_seconds=60)
    tight = RateLimitRule(limit=1, window_seconds=60)
    limiter = RateLimiter(
        default_rule=default, route_rules={"intelligence-views.read": tight}, clock=clock
    )
    assert limiter.check("a", "intelligence-views.read").allowed
    assert limiter.check("a", "intelligence-views.read").allowed is False
    # a different route uses the looser default.
    assert limiter.check("a", "learning.read").allowed is True


def test_manual_reset_clears_bucket():
    clock = FakeClock()
    limiter = RateLimiter(default_rule=RateLimitRule(limit=1, window_seconds=60), clock=clock)
    assert limiter.check("a", "r").allowed
    assert limiter.check("a", "r").allowed is False
    limiter.reset("a", "r")
    assert limiter.check("a", "r").allowed is True


def test_enforce_raises_on_denial():
    clock = FakeClock()
    limiter = RateLimiter(default_rule=RateLimitRule(limit=1, window_seconds=60), clock=clock)
    enforce(limiter, "a", "r")
    with pytest.raises(RateLimitExceeded):
        enforce(limiter, "a", "r")


def test_from_config_builds_rules():
    cfg = {
        "default": {"limit": 10, "window_seconds": 60},
        "routes": {
            "feature-store.export": {
                "limit": 1,
                "window_seconds": 60,
                "algorithm": "fixed_window",
            }
        },
    }
    limiter = RateLimiter.from_config(cfg, clock=FakeClock())
    assert limiter.rule_for("feature-store.export").algorithm is Algorithm.FIXED_WINDOW
    assert limiter.rule_for("anything-else").limit == 10


def test_redis_store_degrades_to_memory_without_client():
    store = RedisRateLimitStore(client=None)
    assert store.degraded is True
    clock = FakeClock()
    limiter = RateLimiter(
        default_rule=RateLimitRule(limit=1, window_seconds=60), store=store, clock=clock
    )
    assert limiter.check("a", "r").allowed
    assert limiter.check("a", "r").allowed is False


def test_redis_store_uses_client_when_present():
    class FakeRedis:
        def __init__(self):
            self.kv = {}

        def get(self, k):
            return self.kv.get(k)

        def set(self, k, v, ex=None):
            self.kv[k] = v

        def delete(self, k):
            self.kv.pop(k, None)

    fake = FakeRedis()
    store = RedisRateLimitStore(client=fake)
    assert store.degraded is False
    limiter = RateLimiter(
        default_rule=RateLimitRule(limit=2, window_seconds=60), store=store, clock=FakeClock()
    )
    assert limiter.check("a", "r").allowed
    assert limiter.check("a", "r").allowed
    assert limiter.check("a", "r").allowed is False
    # state actually landed in the fake backend.
    assert any("a" in k for k in fake.kv)


def test_redis_store_degrades_on_backend_error():
    class BrokenRedis:
        def get(self, k):
            raise RuntimeError("connection refused")

        def set(self, k, v, ex=None):
            raise RuntimeError("connection refused")

        def delete(self, k):
            raise RuntimeError("connection refused")

    store = RedisRateLimitStore(client=BrokenRedis())
    limiter = RateLimiter(
        default_rule=RateLimitRule(limit=1, window_seconds=60), store=store, clock=FakeClock()
    )
    # still serves via in-memory fallback; never raises on the request path.
    assert limiter.check("a", "r").allowed
    assert limiter.check("a", "r").allowed is False
    assert store.degraded is True


def test_invalid_rule_rejected():
    with pytest.raises(ValueError):
        RateLimitRule(limit=0, window_seconds=60)
    with pytest.raises(ValueError):
        RateLimitRule(limit=1, window_seconds=0)


def test_principal_required():
    limiter = RateLimiter(default_rule=RateLimitRule(limit=1, window_seconds=60))
    with pytest.raises(ValueError):
        limiter.check("", "r")
