"""Bridge to the SPINE workflow package (A5) as source, without name collision.

This module's own package is ``app``; the spine workflow package is ALSO ``app``.
Putting the spine workflow dir on ``sys.path`` and doing ``from app.models import
...`` would resolve to the wrong package. So we load the spine workflow modules
under a private namespace (``spine_workflow``) by file location and re-export the
two names B11 needs: the cohort-weakness recommendation builder/signal and the
Recommendation / EvidenceRef / LadderStage models.

Alerts on a dashboard ARE spine recommendations — minted by the spine builder so
they carry the full provenance set and a ladder stage derived from the action's
effect. The view composes; the spine guarantees the invariants. No network, no
build step: the spine is consumed as source.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

# .../classess-school/spine/workflow
_SPINE_WORKFLOW = Path(__file__).resolve().parents[3] / "spine" / "workflow"


def _load() -> types.ModuleType:
    if "spine_workflow" in sys.modules:
        return sys.modules["spine_workflow"]
    pkg_dir = _SPINE_WORKFLOW / "app"
    if not pkg_dir.is_dir():
        raise ImportError(
            f"Spine workflow package not found at {pkg_dir}. The intelligence "
            "views compose spine recommendations and require the spine workflow "
            "source on disk (it is not installed)."
        )
    pkg = types.ModuleType("spine_workflow")
    pkg.__path__ = [str(pkg_dir)]  # type: ignore[attr-defined]
    sys.modules["spine_workflow"] = pkg
    # Order matters: models -> permission -> recommendations (deps first).
    for name in ("models", "permission", "recommendations"):
        spec = importlib.util.spec_from_file_location(
            f"spine_workflow.{name}", pkg_dir / f"{name}.py"
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"spine_workflow.{name}"] = mod
        spec.loader.exec_module(mod)
    return pkg


_load()

from spine_workflow.models import (  # type: ignore  # noqa: E402
    EvidenceRef,
    LadderStage,
    Recommendation,
    RecommendationConfidenceBand,
)
from spine_workflow.recommendations import (  # type: ignore  # noqa: E402
    CohortWeaknessSignal,
    build_cohort_weakness_recommendation,
)

__all__ = [
    "EvidenceRef",
    "LadderStage",
    "Recommendation",
    "RecommendationConfidenceBand",
    "CohortWeaknessSignal",
    "build_cohort_weakness_recommendation",
]
