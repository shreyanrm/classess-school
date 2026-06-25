"""Bootstrap import access to the ai-fabric spine (A4) for the planning module.

Mirrors ``modules/content/_spine.py`` exactly: in the SINGLE DEPLOYABLE many
``app`` packages live in one process, so we load the ai-fabric ``app`` package
under a UNIQUE alias by its explicit filesystem path rather than touching the
shared bare ``app`` name. The planning generators delegate to the orchestrator's
generate-and-verify substrate (the SAME confidence gate the content module uses);
they never re-implement verification.

Import-safe: if the spine is absent, ``SPINE_AVAILABLE`` is False and the
planning generators degrade to a clean refusal (never fabricate a plan).
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys

# .../modules/planning/app/_spine.py -> repo root is four levels up.
_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS, "..", "..", ".."))
_SPINE_DIR = os.path.join(_REPO_ROOT, "spine", "ai-fabric")
_PKG_DIR = os.path.join(_SPINE_DIR, "app")

# Same unique alias the content shim uses — one ai-fabric ``app`` per process.
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
        # Standalone-test compatibility WITHOUT the deployable collision: when the
        # planning package is imported as the bare ``planning`` package (its own
        # test suite), bind the bare ``app`` name to the alias so ``from
        # app.orchestrator import ...`` resolves. In the single deployable
        # (loaded under ``clss_mod_planning``) we never touch the shared name.
        in_deployable = "clss_mod_planning" in sys.modules
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

    Intent = _orchestrator.Intent
    Orchestrator = _orchestrator.Orchestrator

    SPINE_AVAILABLE = True
except Exception:  # pragma: no cover - defensive; keeps import safe
    Intent = None  # type: ignore
    Orchestrator = None  # type: ignore


__all__ = ["SPINE_AVAILABLE", "Intent", "Orchestrator"]
