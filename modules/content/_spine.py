"""Bootstrap import access to the ai-fabric spine (A4) without modifying it.

The spine lives at ``spine/ai-fabric`` and exposes its package as ``app`` (see
its ``conftest.py``, where it is designed to be the SOLE ``app`` on its path).
In the SINGLE DEPLOYABLE many ``app`` packages live in one process (the gateway,
each spine service, the intelligence engine, ...), so adding ``spine/ai-fabric``
to ``sys.path`` and doing a bare ``from app.orchestrator import ...`` would bind
``sys.modules['app']`` to WHICHEVER ``app`` won the import race — a latent,
order-dependent collision that breaks the other ``app`` packages.

Instead we load the ai-fabric ``app`` package under a UNIQUE alias by its
explicit filesystem path (the same discipline as ``backend/loader.py`` and
``modules/learning/_engine.py``), so it never touches the shared bare ``app``
name. The package's internal relative imports (``from .config import ...``) keep
working because the alias is loaded with ``submodule_search_locations``.

Import-safe: if the spine cannot be found, ``SPINE_AVAILABLE`` is False and the
content module degrades to its deterministic, no-fabric path rather than raising
at import time. This module imports FROM the spine; it never mutates it.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys

# .../modules/content/_spine.py -> repo root is three levels up.
_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS, "..", ".."))
_SPINE_DIR = os.path.join(_REPO_ROOT, "spine", "ai-fabric")
_PKG_DIR = os.path.join(_SPINE_DIR, "app")

# Unique alias for the ai-fabric ``app`` package — distinct from every other
# ``app`` package composed into the single deployable.
_AIFABRIC_ALIAS = "clss_aifabric_app"


def _load_aifabric():
    """Load ai-fabric's ``app`` package under the unique alias, by path. Returns
    the package module or ``None`` when absent/unimportable (degrade cleanly)."""
    if _AIFABRIC_ALIAS in sys.modules:
        return sys.modules[_AIFABRIC_ALIAS]
    init = os.path.join(_PKG_DIR, "__init__.py")
    if not os.path.isfile(init):
        return None
    try:
        spec = importlib.util.spec_from_file_location(
            _AIFABRIC_ALIAS, init, submodule_search_locations=[_PKG_DIR]
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_AIFABRIC_ALIAS] = mod
        spec.loader.exec_module(mod)
        # Standalone-test compatibility WITHOUT the deployable collision: the
        # content module's own test suite imports ``from app.orchestrator import
        # ...`` (the spine is designed as the sole ``app`` on its own path). Bind
        # the bare ``app`` name to the alias ONLY when running STANDALONE — i.e.
        # the content module is imported as the bare ``content`` package, not
        # under the deployable's ``clss_mod_content`` alias. In the single
        # deployable (loaded under the alias) we NEVER touch the shared bare
        # ``app`` name, so it cannot collide with any other ``app`` package.
        in_deployable = "clss_mod_content" in sys.modules
        if not in_deployable and "app" not in sys.modules:
            sys.modules["app"] = mod
        return mod
    except Exception:  # pragma: no cover - defensive; keeps import safe
        sys.modules.pop(_AIFABRIC_ALIAS, None)
        return None


SPINE_AVAILABLE = False

try:  # pragma: no cover - exercised indirectly
    if _load_aifabric() is None:
        raise ImportError("ai-fabric spine not importable")
    _orchestrator = importlib.import_module(f"{_AIFABRIC_ALIAS}.orchestrator")
    _capability_registry = importlib.import_module(f"{_AIFABRIC_ALIAS}.capability_registry")
    _verify = importlib.import_module(f"{_AIFABRIC_ALIAS}.verify")

    Candidate = _orchestrator.Candidate
    DeterministicMathProvider = _orchestrator.DeterministicMathProvider
    SpineGenerateResult = _orchestrator.GenerateResult
    Intent = _orchestrator.Intent
    Orchestrator = _orchestrator.Orchestrator
    ProviderAdapter = _orchestrator.ProviderAdapter

    Capability = _capability_registry.Capability
    CapabilityRegistry = _capability_registry.CapabilityRegistry
    Consequence = _capability_registry.Consequence
    default_registry = _capability_registry.default_registry

    ConfidenceGate = _verify.ConfidenceGate
    DeterministicCheck = _verify.DeterministicCheck
    GenerateVerification = _verify.GenerateVerification
    SecondModelChecker = _verify.SecondModelChecker
    AbstainingSecondModel = _verify.AbstainingSecondModel

    SPINE_AVAILABLE = True
except Exception:  # pragma: no cover - defensive; keeps import safe
    Candidate = None  # type: ignore
    DeterministicMathProvider = None  # type: ignore
    SpineGenerateResult = None  # type: ignore
    Intent = None  # type: ignore
    Orchestrator = None  # type: ignore
    ProviderAdapter = None  # type: ignore
    Capability = None  # type: ignore
    CapabilityRegistry = None  # type: ignore
    Consequence = None  # type: ignore
    default_registry = None  # type: ignore
    ConfidenceGate = None  # type: ignore
    DeterministicCheck = None  # type: ignore
    GenerateVerification = None  # type: ignore
    SecondModelChecker = None  # type: ignore
    AbstainingSecondModel = None  # type: ignore


def get_settings(env=None):
    """The ai-fabric spine's settings, via the unique alias — never the bare
    ``app.config`` (which would collide in the single deployable). Returns
    ``None`` when the spine is unavailable so callers degrade cleanly (the
    Gemini provider then has no key and falls back to the template path)."""
    if not SPINE_AVAILABLE:  # pragma: no cover - degraded path
        return None
    config = importlib.import_module(f"{_AIFABRIC_ALIAS}.config")
    return config.get_settings(env) if env is not None else config.get_settings()


__all__ = [
    "SPINE_AVAILABLE",
    "Candidate",
    "DeterministicMathProvider",
    "SpineGenerateResult",
    "Intent",
    "Orchestrator",
    "ProviderAdapter",
    "Capability",
    "CapabilityRegistry",
    "Consequence",
    "default_registry",
    "ConfidenceGate",
    "DeterministicCheck",
    "GenerateVerification",
    "SecondModelChecker",
    "AbstainingSecondModel",
    "get_settings",
]
