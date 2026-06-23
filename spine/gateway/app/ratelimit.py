"""Gateway rate limiting.

Every call passes the wall (Invariant: "every call passes the gateway"). Rate
limiting is enforced at the wall, BEFORE a request is routed to any capability
module, keyed by ``principal + route``.

Two algorithms are provided and selectable per-route via config:

  - ``token_bucket``  : smooth, burst-tolerant. Refills continuously.
  - ``fixed_window``  : simple, predictable. Resets on a wall-clock boundary.

Storage is pluggable via the :class:`RateLimitStore` interface. A Redis-backed
store is described by :class:`RedisRateLimitStore`, which degrades GRACEFULLY to
the in-memory store when no Redis client / connection URL is available
(Invariant: "degrade gracefully with no live keys/DB"). No secret is ever
hardcoded here; the Redis URL is read from the ENV var
``clss.gateway.<env>.redis_url`` by the caller and handed in explicitly.

This module is import-safe: importing it never opens a socket, reads a secret,
or touches a database. All time is injectable for deterministic tests.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Optional, Protocol, Tuple


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


class Algorithm(str, Enum):
    TOKEN_BUCKET = "token_bucket"
    FIXED_WINDOW = "fixed_window"


@dataclass(frozen=True)
class RateLimitRule:
    """A config-driven limit for one logical bucket (a route or a default).

    ``limit``        - max requests allowed inside ``window_seconds``.
    ``window_seconds`` - the window / refill horizon, in seconds.
    ``algorithm``    - which algorithm enforces the rule.
    ``burst``        - token-bucket capacity override; defaults to ``limit``.
    """

    limit: int
    window_seconds: float
    algorithm: Algorithm = Algorithm.TOKEN_BUCKET
    burst: Optional[int] = None

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("rate limit `limit` must be positive")
        if self.window_seconds <= 0:
            raise ValueError("rate limit `window_seconds` must be positive")
        if self.burst is not None and self.burst <= 0:
            raise ValueError("rate limit `burst` must be positive")

    @property
    def capacity(self) -> int:
        return int(self.burst) if self.burst is not None else int(self.limit)

    @property
    def refill_per_second(self) -> float:
        return self.limit / self.window_seconds


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    limit: int
    # Seconds until the caller may retry (0 when allowed and tokens remain).
    retry_after: float
    # Wall-clock epoch at which the bucket fully resets.
    reset_at: float


# --------------------------------------------------------------------------- #
# Storage interface
# --------------------------------------------------------------------------- #


@dataclass
class _BucketState:
    tokens: float
    updated_at: float
    # fixed-window only
    window_start: float = 0.0
    window_count: int = 0


class RateLimitStore(Protocol):
    """Pluggable storage for limiter state.

    Implementations MUST be safe under concurrent access for a single process.
    Cross-process atomicity is the backend's responsibility (Redis Lua / INCR).
    """

    def get(self, key: str) -> Optional[_BucketState]: ...

    def set(self, key: str, state: _BucketState, ttl_seconds: float) -> None: ...

    def reset(self, key: str) -> None: ...

    def clear(self) -> None: ...


class InMemoryRateLimitStore:
    """Process-local, thread-safe store. The default and the degrade target."""

    def __init__(self) -> None:
        self._data: Dict[str, _BucketState] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[_BucketState]:
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, state: _BucketState, ttl_seconds: float) -> None:
        # ttl is advisory for the in-memory store; entries are small and
        # overwritten on each touch. We keep the signature uniform with Redis.
        with self._lock:
            self._data[key] = state

    def reset(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class RedisRateLimitStore:
    """Redis-backed store that degrades to in-memory.

    Pass a live ``redis`` client (any object exposing ``get``/``set``/``delete``
    and ``pipeline`` is acceptable). When ``client`` is ``None`` -- e.g. no
    ``clss.gateway.<env>.redis_url`` is configured, or the connection is
    unavailable -- this transparently falls back to an in-memory store so the
    gateway keeps serving instead of failing closed on infrastructure.

    State is serialized as a compact string. This intentionally avoids importing
    ``redis`` so the module stays import-safe with no dependency installed.
    """

    def __init__(self, client: Optional[object] = None) -> None:
        self._client = client
        self._fallback = InMemoryRateLimitStore()
        # Whether we are currently using Redis or have degraded.
        self.degraded = client is None

    @staticmethod
    def _encode(state: _BucketState) -> str:
        return "{:.6f}|{:.6f}|{:.6f}|{:d}".format(
            state.tokens, state.updated_at, state.window_start, state.window_count
        )

    @staticmethod
    def _decode(raw: str) -> _BucketState:
        tokens, updated_at, window_start, window_count = raw.split("|")
        return _BucketState(
            tokens=float(tokens),
            updated_at=float(updated_at),
            window_start=float(window_start),
            window_count=int(window_count),
        )

    def get(self, key: str) -> Optional[_BucketState]:
        if self._client is None:
            return self._fallback.get(key)
        try:
            raw = self._client.get(key)  # type: ignore[attr-defined]
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return self._decode(raw)
        except Exception:
            # Backend hiccup -> degrade to local, never fail the request path.
            self.degraded = True
            return self._fallback.get(key)

    def set(self, key: str, state: _BucketState, ttl_seconds: float) -> None:
        if self._client is None:
            self._fallback.set(key, state, ttl_seconds)
            return
        try:
            self._client.set(  # type: ignore[attr-defined]
                key, self._encode(state), ex=max(1, int(ttl_seconds))
            )
        except Exception:
            self.degraded = True
            self._fallback.set(key, state, ttl_seconds)

    def reset(self, key: str) -> None:
        if self._client is None:
            self._fallback.reset(key)
            return
        try:
            self._client.delete(key)  # type: ignore[attr-defined]
        except Exception:
            self.degraded = True
            self._fallback.reset(key)

    def clear(self) -> None:
        self._fallback.clear()


# --------------------------------------------------------------------------- #
# Limiter
# --------------------------------------------------------------------------- #


# Clock type: a zero-arg callable returning epoch seconds. Injectable for tests.
Clock = Callable[[], float]


class RateLimiter:
    """Config-driven, per-principal-per-route limiter enforced at the wall."""

    KEY_PREFIX = "clss:gw:rl"

    def __init__(
        self,
        *,
        default_rule: RateLimitRule,
        route_rules: Optional[Dict[str, RateLimitRule]] = None,
        store: Optional[RateLimitStore] = None,
        clock: Optional[Clock] = None,
    ) -> None:
        self.default_rule = default_rule
        self.route_rules: Dict[str, RateLimitRule] = dict(route_rules or {})
        self.store: RateLimitStore = store or InMemoryRateLimitStore()
        self._clock: Clock = clock or time.monotonic
        self._lock = threading.RLock()

    # -- config --------------------------------------------------------- #

    def rule_for(self, route: str) -> RateLimitRule:
        return self.route_rules.get(route, self.default_rule)

    def register_route(
        self, route: str, rule: RateLimitRule, overwrite: bool = True
    ) -> None:
        # Explicitly configured limits (from config / the caller) take
        # precedence: capability-declared defaults are only applied when no
        # rule is already present (overwrite=False).
        if not overwrite and route in self.route_rules:
            return
        self.route_rules[route] = rule

    @classmethod
    def from_config(cls, config: dict, **kwargs) -> "RateLimiter":
        """Build from a plain dict (e.g. parsed YAML/JSON).

        Expected shape::

            {
              "default": {"limit": 100, "window_seconds": 60,
                          "algorithm": "token_bucket"},
              "routes": {
                "intelligence-views.read": {"limit": 30, "window_seconds": 60},
                ...
              }
            }
        """

        def _mk(d: dict) -> RateLimitRule:
            return RateLimitRule(
                limit=int(d["limit"]),
                window_seconds=float(d["window_seconds"]),
                algorithm=Algorithm(d.get("algorithm", Algorithm.TOKEN_BUCKET)),
                burst=(int(d["burst"]) if d.get("burst") is not None else None),
            )

        default_rule = _mk(config["default"])
        route_rules = {r: _mk(d) for r, d in (config.get("routes") or {}).items()}
        return cls(default_rule=default_rule, route_rules=route_rules, **kwargs)

    # -- key ------------------------------------------------------------ #

    def _key(self, principal: str, route: str) -> str:
        # principal is a canonical_uuid or service id -- never PII.
        return f"{self.KEY_PREFIX}:{route}:{principal}"

    # -- core ----------------------------------------------------------- #

    def check(
        self, principal: str, route: str, cost: int = 1
    ) -> RateLimitDecision:
        """Atomically (per process) account ``cost`` against the bucket.

        Returns a decision; does NOT raise. The wall converts a denied decision
        into HTTP 429 with ``Retry-After``.
        """
        if not principal:
            raise ValueError("principal is required for rate limiting")
        rule = self.rule_for(route)
        key = self._key(principal, route)
        now = self._clock()

        with self._lock:
            if rule.algorithm is Algorithm.TOKEN_BUCKET:
                decision = self._check_token_bucket(key, rule, now, cost)
            else:
                decision = self._check_fixed_window(key, rule, now, cost)
            return decision

    def _check_token_bucket(
        self, key: str, rule: RateLimitRule, now: float, cost: int
    ) -> RateLimitDecision:
        state = self.store.get(key)
        capacity = float(rule.capacity)
        if state is None:
            state = _BucketState(tokens=capacity, updated_at=now)
        else:
            elapsed = max(0.0, now - state.updated_at)
            refilled = elapsed * rule.refill_per_second
            state.tokens = min(capacity, state.tokens + refilled)
            state.updated_at = now

        if state.tokens >= cost:
            state.tokens -= cost
            allowed = True
            retry_after = 0.0
        else:
            allowed = False
            deficit = cost - state.tokens
            retry_after = deficit / rule.refill_per_second

        remaining = int(state.tokens)
        # Time for the bucket to refill to capacity from here.
        missing = capacity - state.tokens
        reset_in = missing / rule.refill_per_second if missing > 0 else 0.0
        self.store.set(key, state, ttl_seconds=rule.window_seconds * 2)
        return RateLimitDecision(
            allowed=allowed,
            remaining=remaining,
            limit=rule.capacity,
            retry_after=retry_after,
            reset_at=now + reset_in,
        )

    def _check_fixed_window(
        self, key: str, rule: RateLimitRule, now: float, cost: int
    ) -> RateLimitDecision:
        state = self.store.get(key)
        window = rule.window_seconds
        window_start = now - (now % window)
        if state is None or state.window_start != window_start:
            state = _BucketState(
                tokens=0.0,
                updated_at=now,
                window_start=window_start,
                window_count=0,
            )

        reset_at = window_start + window
        if state.window_count + cost <= rule.limit:
            state.window_count += cost
            allowed = True
            retry_after = 0.0
        else:
            allowed = False
            retry_after = max(0.0, reset_at - now)

        remaining = max(0, rule.limit - state.window_count)
        state.updated_at = now
        self.store.set(key, state, ttl_seconds=window * 2)
        return RateLimitDecision(
            allowed=allowed,
            remaining=remaining,
            limit=rule.limit,
            retry_after=retry_after,
            reset_at=reset_at,
        )

    # -- admin ---------------------------------------------------------- #

    def reset(self, principal: str, route: str) -> None:
        self.store.reset(self._key(principal, route))

    def reset_all(self) -> None:
        self.store.clear()


class RateLimitExceeded(Exception):
    """Raised by :meth:`RateLimiter.enforce` when a bucket is exhausted."""

    def __init__(self, decision: RateLimitDecision):
        self.decision = decision
        super().__init__(
            f"rate limit exceeded; retry after {decision.retry_after:.2f}s"
        )


def enforce(
    limiter: RateLimiter, principal: str, route: str, cost: int = 1
) -> RateLimitDecision:
    """Convenience: check and raise on denial. Used by the wall pipeline."""
    decision = limiter.check(principal, route, cost=cost)
    if not decision.allowed:
        raise RateLimitExceeded(decision)
    return decision
