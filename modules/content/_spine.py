"""Bootstrap import access to the ai-fabric spine (A4) without modifying it.

The spine lives at ``spine/ai-fabric`` and exposes its package as ``app``
(see its ``conftest.py``). This module adds that directory to ``sys.path`` so
``from app.orchestrator import ...`` resolves, and re-exports the handful of
symbols the content module wires to. Import-safe: if the spine cannot be found,
``SPINE_AVAILABLE`` is False and the content module degrades to its
deterministic, no-fabric path rather than raising at import time.

This module imports FROM the spine; it never mutates it.
"""

from __future__ import annotations

import os
import sys

# .../modules/content/_spine.py -> repo root is three levels up.
_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_THIS, "..", ".."))
_SPINE_DIR = os.path.join(_REPO_ROOT, "spine", "ai-fabric")

if _SPINE_DIR not in sys.path and os.path.isdir(_SPINE_DIR):
    sys.path.insert(0, _SPINE_DIR)

SPINE_AVAILABLE = False

try:  # pragma: no cover - exercised indirectly
    from app.orchestrator import (  # type: ignore
        Candidate,
        DeterministicMathProvider,
        GenerateResult as SpineGenerateResult,
        Intent,
        Orchestrator,
        ProviderAdapter,
    )
    from app.capability_registry import (  # type: ignore
        Capability,
        CapabilityRegistry,
        Consequence,
        default_registry,
    )
    from app.verify import (  # type: ignore
        ConfidenceGate,
        DeterministicCheck,
        GenerateVerification,
        SecondModelChecker,
        AbstainingSecondModel,
    )

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
]
