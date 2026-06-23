"""Bridge to the intelligence engine (spine A3) — consumed, never modified.

The Learning module does NOT author mastery. The evidence -> mastery -> gap
judgment is CORE and lives in ``spine/intelligence`` (the engine that replays
the immutable event log into a learner profile). This adapter imports that
engine read-only and exposes the few entry points the learning flows need:

  - ``compute_mastery`` / ``build_profile`` / ``build_topic_projection``
  - the ``EventEnvelope`` / ``PrerequisiteGraph`` models for replay input
  - ``detect_gaps`` for gap-aware item selection

It NEVER mutates the engine and adds no identity beyond the opaque token. Every
function here is a thin pass-through to the spine.

DEGRADATION (no live provider / no pydantic): the spine engine depends on
pydantic. If it cannot be imported (dependency absent), ``available()`` returns
False and the learning flows fall back to their own deterministic, dependency-
free heuristics over plain evidence records — clearly labelled degraded — so the
module stays import-safe and the deterministic paths still work offline.

The engine itself reaches the event store THROUGH the gateway and holds no
credentials; in the degraded in-memory path it makes no network call at all.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Any


def _spine_intelligence_root() -> str | None:
    """Locate ``spine/intelligence`` (whose package is ``app``) relative to this
    file, walking up to the repo root. Returns the directory to put on sys.path,
    or None if not found."""
    here = os.path.dirname(os.path.abspath(__file__))
    # modules/learning -> modules -> repo root.
    cur = here
    for _ in range(6):
        candidate = os.path.join(cur, "spine", "intelligence")
        if os.path.isdir(os.path.join(candidate, "app")):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


@lru_cache(maxsize=1)
def _load() -> Any | None:
    """Import the spine intelligence ``app`` package, putting its root on
    sys.path. Cached. Returns the module object or None when unavailable
    (missing dependency / missing spine)."""
    root = _spine_intelligence_root()
    if root is None:
        return None
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        import app  # type: ignore  # the spine intelligence package

        return app
    except Exception:
        # Most likely pydantic is not installed in this environment. The flows
        # degrade to their own deterministic heuristics.
        return None


def available() -> bool:
    """True when the CORE intelligence engine is importable and usable."""
    return _load() is not None


def degraded_reason() -> str | None:
    """A human-readable reason the engine is unavailable, or None when present.
    Names the dependency, never a secret value."""
    if available():
        return None
    if _spine_intelligence_root() is None:
        return "spine/intelligence engine not found on disk"
    return (
        "spine/intelligence engine present but not importable "
        "(its pydantic dependency is not installed); using the module's "
        "deterministic fallback heuristics"
    )


# --- Thin pass-throughs (only callable when available()) -------------------
def engine() -> Any:
    app = _load()
    if app is None:  # pragma: no cover - guarded by available() at call sites
        raise RuntimeError(degraded_reason() or "intelligence engine unavailable")
    return app


def make_envelope(data: dict[str, Any]) -> Any:
    """Validate a raw event dict into the engine's ``EventEnvelope`` model."""
    return engine().EventEnvelope.model_validate(data)


def compute_mastery(events: list[Any], *, subject: Any, topic_id: Any, **kw: Any) -> Any:
    return engine().compute_mastery(events, subject=subject, topic_id=topic_id, **kw)


def build_profile(events: list[Any], *, subject: Any, **kw: Any) -> Any:
    return engine().build_profile(events, subject=subject, **kw)


def build_topic_projection(events: list[Any], *, subject: Any, topic_id: Any, **kw: Any) -> Any:
    return engine().build_topic_projection(events, subject=subject, topic_id=topic_id, **kw)


def detect_gaps(events: list[Any], *, subject: Any, topic_id: Any, **kw: Any) -> Any:
    return engine().detect_gaps(events, subject=subject, topic_id=topic_id, **kw)


def prerequisite_graph(edges: list[dict[str, Any]] | None = None) -> Any:
    app = engine()
    built = [app.PrerequisiteEdge(**e) for e in (edges or [])]
    return app.PrerequisiteGraph(edges=built)
