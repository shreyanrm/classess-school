"""In-process loader for the spine services and capability modules.

The repository is a set of independent Python libraries, each shipping its own
``app`` package and each *designed to be the sole* ``app`` on ``sys.path`` (see
the per-module ``conftest.py``). To compose them into ONE deployable process we
cannot put them all on the path as ``app`` — they would collide. Instead we load
each ``app`` package under a unique alias (e.g. ``clss_svc_identity``) using
``importlib`` with an explicit ``submodule_search_locations`` so that the
packages' internal relative imports (``from .config import ...``) keep working.

This module performs NO I/O and reads NO secret value at import: it only resolves
filesystem paths and imports pure-python packages (which are themselves
import-safe). A missing optional module degrades to ``None`` rather than crashing
the whole process — the gateway is still the wall and still serves ``/health``.

LAW: import-safe; degrade cleanly when a dependency is absent.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import os
import sys
from types import ModuleType
from typing import Optional

logger = logging.getLogger("clss.backend.loader")

# Repo root is the parent of this ``backend`` directory.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Logical name -> (alias, package directory) for the spine FastAPI services.
SPINE_APPS: dict[str, str] = {
    "identity": "spine/identity/app",
    "event-store": "spine/event-store/app",
}

# The gateway package (the wall) — loaded under its own alias.
GATEWAY_PKG_DIR = "spine/gateway/app"
GATEWAY_ALIAS = "clss_gateway_app"

# Capability modules wired behind the wall. Each is a pure-python library; the
# wall enforces access, the module stays thin (per the capability registry).
CAPABILITY_MODULES: tuple[str, ...] = (
    "institution",
    "ontology-ingestion",
    "scheduling",
    "content",
    "planning",
    "coursework",
    "learning",
    "attendance",
    "classroom",
    "learner-record",
    "communication",
)


def _alias_for(prefix: str, name: str) -> str:
    return f"clss_{prefix}_{name.replace('-', '_')}"


def load_package(alias: str, pkg_dir_rel: str) -> Optional[ModuleType]:
    """Load the ``app`` package at ``pkg_dir_rel`` under ``alias``.

    Returns the imported module, or ``None`` if the package is absent or fails to
    import (degrade cleanly — never crash the deployable).
    """
    pkg_dir = os.path.join(REPO_ROOT, pkg_dir_rel)
    init = os.path.join(pkg_dir, "__init__.py")
    if not os.path.isfile(init):
        logger.warning("capability package absent (skipping): %s", pkg_dir_rel)
        return None
    if alias in sys.modules:
        return sys.modules[alias]
    try:
        spec = importlib.util.spec_from_file_location(
            alias, init, submodule_search_locations=[pkg_dir]
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[alias] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:  # pragma: no cover - defensive degrade path
        sys.modules.pop(alias, None)
        logger.warning("failed to load %s (degrading): %s", pkg_dir_rel, exc)
        return None


def load_gateway() -> ModuleType:
    """Load the gateway (wall) package. The wall is required: without it there is
    no front door, so this is allowed to raise."""
    mod = load_package(GATEWAY_ALIAS, GATEWAY_PKG_DIR)
    if mod is None:  # pragma: no cover - the gateway must always be present
        raise RuntimeError("gateway package could not be loaded; cannot start the wall")
    return mod


def load_spine_app(name: str) -> Optional[ModuleType]:
    """Load a spine FastAPI service's ``app.main`` module under a unique alias."""
    rel = SPINE_APPS[name]
    alias = _alias_for("svc", name)
    pkg = load_package(alias, rel)
    if pkg is None:
        return None
    try:
        return importlib.import_module(f"{alias}.main")
    except Exception as exc:  # pragma: no cover - degrade path
        logger.warning("spine service %s failed to expose app (degrading): %s", name, exc)
        return None


def _capability_pkg_dir(name: str) -> Optional[str]:
    """Resolve where a capability module's importable package lives.

    Two on-disk shapes exist in this repo and BOTH must load:

      * nested:  ``modules/<name>/app/__init__.py``   (institution, scheduling, ...)
      * flat:    ``modules/<name>/__init__.py``        (content, learning)

    Prefer the nested ``app`` package when present (it is the canonical capability
    surface); otherwise fall back to the flat module package. Returns the repo-
    relative package dir, or ``None`` when neither exists.
    """
    nested = os.path.join(REPO_ROOT, "modules", name, "app", "__init__.py")
    if os.path.isfile(nested):
        return f"modules/{name}/app"
    flat = os.path.join(REPO_ROOT, "modules", name, "__init__.py")
    if os.path.isfile(flat):
        return f"modules/{name}"
    return None


def load_capability_module(name: str) -> Optional[ModuleType]:
    """Load a capability module under a unique alias, whether its package is the
    nested ``modules/<name>/app`` or the flat ``modules/<name>`` (detect which
    exists and import the right one). Degrades to ``None`` if neither is present
    or the package fails to import — the wall still denies its routes by default.
    """
    alias = _alias_for("mod", name)
    pkg_dir_rel = _capability_pkg_dir(name)
    if pkg_dir_rel is None:
        logger.warning("capability module absent (no app/ or flat package): modules/%s", name)
        return None
    return load_package(alias, pkg_dir_rel)
