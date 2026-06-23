"""Tests for the verified-content response cache.

The cache holds ONLY verified artifacts and is keyed by a verified-content hash.
A hit returns the gate-cleared artifact; a tampered entry fails closed.

Import-safe, no network.
"""

from __future__ import annotations

from app.cache import (
    VerifiedResponseCache,
    request_fingerprint,
    verified_content_hash,
)


def _args(content):
    return dict(
        capability="content.generate-practice-item",
        task_class="content.generate-practice-item",
        tier="mid",
        payload={"topic": "fractions"},
        content=content,
    )


def test_key_is_stable_and_content_sensitive():
    a = verified_content_hash(**_args({"answer": 144}))
    b = verified_content_hash(**_args({"answer": 144}))
    c = verified_content_hash(**_args({"answer": 140}))
    assert a == b           # same request + content -> same key
    assert a != c           # different content -> different key


def test_fingerprint_ignores_dict_order():
    f1 = request_fingerprint(
        capability="x", task_class="t", tier="mid", payload={"a": 1, "b": 2}
    )
    f2 = request_fingerprint(
        capability="x", task_class="t", tier="mid", payload={"b": 2, "a": 1}
    )
    assert f1 == f2


def test_put_then_get_returns_verified_artifact():
    cache = VerifiedResponseCache()
    cache.put(confidence=0.95, **_args({"answer": 144}))
    hit = cache.get(**_args({"answer": 144}))
    assert hit is not None
    assert hit.content == {"answer": 144}
    assert hit.confidence == 0.95
    assert cache.hits == 1
    assert cache.misses == 0


def test_miss_on_different_content():
    cache = VerifiedResponseCache()
    cache.put(confidence=0.95, **_args({"answer": 144}))
    assert cache.get(**_args({"answer": 999})) is None
    assert cache.misses == 1


def test_lru_eviction_bounds_size():
    cache = VerifiedResponseCache(max_entries=2)
    for n in range(3):
        cache.put(
            capability="c", task_class="t", tier="mid",
            payload={"n": n}, content={"v": n}, confidence=0.9,
        )
    assert len(cache) == 2
    # The first inserted entry was evicted.
    assert cache.get(capability="c", task_class="t", tier="mid", payload={"n": 0}, content={"v": 0}) is None
    assert cache.get(capability="c", task_class="t", tier="mid", payload={"n": 2}, content={"v": 2}) is not None


def test_no_secret_in_cache_key():
    # The key is a hex digest; it carries no provider material.
    key = verified_content_hash(**_args({"answer": 1}))
    assert all(ch in "0123456789abcdef" for ch in key)
    assert len(key) == 64
