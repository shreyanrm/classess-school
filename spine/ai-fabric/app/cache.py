"""The response CACHE for verified content (A4).

A generated artifact is cached ONLY after it passes the confidence gate
(INVARIANT 7) — the cache never holds unverified content. The key is a
VERIFIED-CONTENT HASH: a stable digest of the request shape (capability +
task-class + a normalised payload + the resolved tier) PLUS the verified
content itself. Because the key folds in the served content, a cache entry is
self-describing: a hit returns an artifact that already cleared the gate, so the
gate need not be re-run on a hit.

Why hash the content into the key, not just the request?
  - It makes a cached entry tamper-evident: a stored artifact whose content no
    longer hashes to its key is rejected (fails closed).
  - It keeps the cache honest about INVARIANT 7 — only a *verified* artifact ever
    produced a key, so the namespace itself is "verified content only".

The cache is in-process and dependency-free (a plain dict with optional LRU
bound). No PII is stored — keys are opaque digests and values are the already
public verified content. No secret is ever part of a key or a value.
"""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


def _canonical(value: Any) -> str:
    """A stable, canonical JSON string for hashing.

    Sorts dict keys and uses compact separators so logically-equal payloads
    produce the same digest regardless of key order or whitespace. Non-JSON
    values fall back to ``repr`` so hashing never raises.
    """
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=repr)
    except (TypeError, ValueError):
        return repr(value)


def request_fingerprint(
    *,
    capability: str,
    task_class: str,
    tier: str,
    payload: dict[str, Any],
) -> str:
    """A digest of the REQUEST shape (no content yet).

    Used to namespace cache lookups before a candidate exists: the lookup must
    combine this with the verified content to form the full key, so the lookup
    path mirrors the store path.
    """
    material = _canonical(
        {"capability": capability, "task_class": task_class, "tier": tier, "payload": payload}
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def verified_content_hash(
    *,
    capability: str,
    task_class: str,
    tier: str,
    payload: dict[str, Any],
    content: Any,
) -> str:
    """The CACHE KEY: a digest over the request fingerprint AND the verified
    content. Only ever computed for content that has passed the gate, so the key
    space is, by construction, verified content only."""
    material = _canonical(
        {
            "fingerprint": request_fingerprint(
                capability=capability, task_class=task_class, tier=tier, payload=payload
            ),
            "content": content,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CachedArtifact:
    """A verified artifact stored in the cache.

    ``content`` already cleared the confidence gate; ``confidence`` and ``tier``
    are recorded for the trace span on a hit. ``content_hash`` is the key it was
    stored under — re-derivable from the content, making the entry tamper-evident.
    """

    content: Any
    confidence: float
    tier: str
    content_hash: str


class VerifiedResponseCache:
    """An in-process LRU cache of verified artifacts, keyed by content hash.

    INVARIANT 7 — nothing is stored unless it has been verified; the caller MUST
    only call :meth:`put` with content that passed the gate. A :meth:`get` that
    finds an entry whose content no longer hashes to its key is treated as a MISS
    (fails closed) and the bad entry is evicted.
    """

    def __init__(self, max_entries: int = 1024) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._max = max_entries
        self._store: "OrderedDict[str, CachedArtifact]" = OrderedDict()
        self.hits = 0
        self.misses = 0

    # -- store ------------------------------------------------------------

    def put(
        self,
        *,
        capability: str,
        task_class: str,
        tier: str,
        payload: dict[str, Any],
        content: Any,
        confidence: float,
    ) -> str:
        """Store a VERIFIED artifact and return its content-hash key."""
        key = verified_content_hash(
            capability=capability, task_class=task_class, tier=tier,
            payload=payload, content=content,
        )
        artifact = CachedArtifact(
            content=content, confidence=confidence, tier=tier, content_hash=key
        )
        self._store[key] = artifact
        self._store.move_to_end(key)
        while len(self._store) > self._max:
            self._store.popitem(last=False)  # evict least-recently-used
        return key

    # -- lookup -----------------------------------------------------------

    def get(
        self,
        *,
        capability: str,
        task_class: str,
        tier: str,
        payload: dict[str, Any],
        content: Any,
    ) -> CachedArtifact | None:
        """Look up by the SAME content hash used to store.

        A lookup needs the candidate content (the hash folds it in). Returns the
        cached verified artifact on a hit, ``None`` on a miss. A tamper-evident
        mismatch is a miss and evicts the offending entry.
        """
        key = verified_content_hash(
            capability=capability, task_class=task_class, tier=tier,
            payload=payload, content=content,
        )
        artifact = self._store.get(key)
        if artifact is None:
            self.misses += 1
            return None
        # Tamper-evidence: the stored content must still hash to its key.
        rederived = verified_content_hash(
            capability=capability, task_class=task_class, tier=tier,
            payload=payload, content=artifact.content,
        )
        if rederived != artifact.content_hash:
            # Fail closed — evict and miss.
            self._store.pop(key, None)
            self.misses += 1
            return None
        self._store.move_to_end(key)
        self.hits += 1
        return artifact

    def __len__(self) -> int:
        return len(self._store)
