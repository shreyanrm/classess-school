"""Bind the intelligence engine (spine A3) as the upstream interface.

The feature store CONSUMES the intelligence engine — it does not reimplement
mastery, gaps, or evidence weighting. One definition, computed the same
everywhere: the feature store reads the engine's projections and turns them into
derived, versioned, point-in-time-correct features.

The intelligence package lives in a sibling spine module (``spine/intelligence``)
and ships as a plain ``app`` package with no build step. Both that engine and
this feature store name their top-level package ``app``; importing the engine's
``app`` naively would collide with ours. So we load the engine package under a
DISTINCT top-level name (``clss_intelligence_engine``) using importlib's spec
machinery, pointed straight at the engine's ``app`` directory. The engine source
is NEVER modified and never imported under the bare name ``app``.

If the engine cannot be located, this raises a clear, named error rather than
silently degrading — a missing upstream is a defect, not a degraded mode.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

# The engine package root: the sibling ``spine/intelligence`` module, whose
# importable package is its ``app`` directory.
_THIS = Path(__file__).resolve()
_FEATURE_STORE_ROOT = _THIS.parents[1]          # .../spine/feature-store
_SPINE_ROOT = _FEATURE_STORE_ROOT.parent         # .../spine
_ENGINE_APP_DIR = _SPINE_ROOT / "intelligence" / "app"

# The distinct top-level name we load the engine under, so it never collides with
# this feature store's own ``app`` package.
_ENGINE_PKG = "clss_intelligence_engine"


def _load_engine() -> ModuleType:
    """Load the intelligence engine's ``app`` package under ``_ENGINE_PKG``.

    We register a package spec whose ``submodule_search_locations`` point at the
    engine's ``app`` directory, then load its ``__init__``. Submodules import each
    other with relative imports (``from .models import ...``), which resolve
    correctly because the package's search path is the engine ``app`` dir.
    """
    if _ENGINE_PKG in sys.modules:
        return sys.modules[_ENGINE_PKG]

    init_path = _ENGINE_APP_DIR / "__init__.py"
    if not init_path.exists():
        raise ModuleNotFoundError(
            "Could not locate the intelligence engine. Expected the spine "
            f"intelligence package at {_ENGINE_APP_DIR!s} (containing __init__.py). "
            "The feature store CONSUMES this engine and must not reimplement it."
        )

    spec = importlib.util.spec_from_file_location(
        _ENGINE_PKG,
        init_path,
        submodule_search_locations=[str(_ENGINE_APP_DIR)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to build an import spec for {init_path!s}.")

    module = importlib.util.module_from_spec(spec)
    # Register BEFORE executing so the package's own relative submodule imports
    # (resolved as ``_ENGINE_PKG.<sub>``) find the parent package.
    sys.modules[_ENGINE_PKG] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        # Don't leave a half-initialized package registered.
        sys.modules.pop(_ENGINE_PKG, None)
        raise
    return module


_engine = _load_engine()


def _engine_submodule(name: str) -> ModuleType:
    """Import an engine submodule (e.g. 'evidence') under the aliased package."""
    return importlib.import_module(f"{_ENGINE_PKG}.{name}")


# Re-export the public engine surface the feature store builds upon. These are
# the ONLY engine symbols the rest of the package references — a single, audited
# seam onto the upstream contract.
EventEnvelope = _engine.EventEnvelope
AttemptPayload = _engine.AttemptPayload
ScoreRecordedPayload = _engine.ScoreRecordedPayload
OntologyRef = _engine.OntologyRef
MasteryBand = _engine.MasteryBand
MasteryDimensions = _engine.MasteryDimensions
MasteryReading = _engine.MasteryReading
MasteryResult = _engine.MasteryResult
MasteryWeights = _engine.MasteryWeights
GapType = _engine.GapType
GapResult = _engine.GapResult
GapEvidence = _engine.GapEvidence
PrerequisiteGraph = _engine.PrerequisiteGraph
PrerequisiteEdge = _engine.PrerequisiteEdge

compute_mastery = _engine.compute_mastery
detect_gaps = _engine.detect_gaps
collect_evidence = _engine.collect_evidence
build_topic_projection = _engine.build_topic_projection
build_profile = _engine.build_profile
LearnerProfile = _engine.LearnerProfile
TopicProjection = _engine.TopicProjection

# Evidence-layer internals reused for point-in-time feature derivation. We READ
# them from the engine; we never redefine them.
_evidence = _engine_submodule("evidence")
EvidenceItem = _evidence.EvidenceItem
RECENCY_HALF_LIFE = _evidence.RECENCY_HALF_LIFE
assistance_rank = _evidence.assistance_rank

__all__ = [
    "EventEnvelope",
    "AttemptPayload",
    "ScoreRecordedPayload",
    "OntologyRef",
    "MasteryBand",
    "MasteryDimensions",
    "MasteryReading",
    "MasteryResult",
    "MasteryWeights",
    "GapType",
    "GapResult",
    "GapEvidence",
    "PrerequisiteGraph",
    "PrerequisiteEdge",
    "compute_mastery",
    "detect_gaps",
    "collect_evidence",
    "build_topic_projection",
    "build_profile",
    "LearnerProfile",
    "TopicProjection",
    "EvidenceItem",
    "RECENCY_HALF_LIFE",
    "assistance_rank",
]
