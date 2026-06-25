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

import importlib.util
import os
import sys
from functools import lru_cache
from typing import Any

# The spine intelligence package ships as ``app`` (designed to be the sole
# ``app`` on its own path). In the SINGLE DEPLOYABLE many ``app`` packages live
# in one process (the gateway, each spine service, ...), so a bare ``import app``
# here would bind whichever ``app`` won the import race to ``sys.modules['app']``
# — a latent, order-dependent collision. We load the engine under a UNIQUE alias
# instead (same discipline as ``backend/loader.py``), so it never touches the
# shared bare ``app`` name. Distinct from the deployable's own alias to avoid
# clobbering it when both run in one process.
_ENGINE_ALIAS = "clss_intelligence_engine"


def _spine_intelligence_root() -> str | None:
    """Locate ``spine/intelligence`` (whose package is ``app``) relative to this
    file, walking up to the repo root. Returns the directory containing the
    ``app`` package, or None if not found."""
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
    """Import the spine intelligence ``app`` package UNDER A UNIQUE ALIAS, by its
    explicit filesystem path. Cached. Returns the module object or None when
    unavailable (missing dependency / missing spine).

    Loading by path + alias (instead of a bare ``import app`` after a
    ``sys.path`` insert) means this never binds — or reads — the shared top-level
    ``app`` name, so it cannot collide with the other ``app`` packages composed
    into the single deployable. If the engine was already loaded under this alias
    in-process, we reuse it."""
    if _ENGINE_ALIAS in sys.modules:
        return sys.modules[_ENGINE_ALIAS]
    root = _spine_intelligence_root()
    if root is None:
        return None
    pkg_dir = os.path.join(root, "app")
    init = os.path.join(pkg_dir, "__init__.py")
    if not os.path.isfile(init):
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            _ENGINE_ALIAS, init, submodule_search_locations=[pkg_dir]
        )
        assert spec and spec.loader
        engine = importlib.util.module_from_spec(spec)
        sys.modules[_ENGINE_ALIAS] = engine
        spec.loader.exec_module(engine)
        return engine
    except Exception:
        # Most likely pydantic is not installed in this environment. The flows
        # degrade to their own deterministic heuristics. Drop the half-bound
        # alias so a later retry under a fixed env can succeed.
        sys.modules.pop(_ENGINE_ALIAS, None)
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
