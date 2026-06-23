"""Classess School — Learning module (B7, adaptive engine CORE).

Learning is POSE -> STRUGGLE -> REVEAL, never explain-first. Practice
contributes EVIDENCE, not a completion tick. The assistance ladder FADES as
competence grows. Spaced retrieval runs against the real forgetting curve.

This package is a capability module (B7). It does NOT author mastery — the
CORE judgment lives in the intelligence engine (spine A3, consumed read-only
through ``spine.intelligence``). This module orchestrates the learner-facing
flow and EMITS evidence events (attempt / practice / mastery-evidence) keyed to
the opaque ``canonical_uuid`` only, behind the contract shapes.

Public surface:

  - ``learn``      : the pose -> struggle -> reveal flow controller.
  - ``practice``   : adaptive next-item selection by mastery + gaps.
  - ``ladder``     : the assistance-ladder controller (fades support; always
                     declares helping-vs-evaluating).
  - ``revision``   : spaced-retrieval scheduler against the forgetting curve.
  - ``readiness``  : exam-readiness forecasting from mastery + coverage.
  - ``events``     : emit attempt/practice/mastery-evidence events.

Import-safe: importing this package performs no I/O, opens no connection, and
reads no secret value. The pydantic-backed intelligence engine and event
shapes are imported lazily by the submodules that need them, so the surface
classes here stay importable for tooling even before dependencies are present.
"""

from __future__ import annotations

from .config import LearningSettings, get_settings

__all__ = [
    "LearningSettings",
    "get_settings",
    # Submodules are imported by name (``from learning import learn``) rather
    # than eagerly here, so a missing optional dependency in one path never
    # breaks importing another. Listed for discoverability.
    "learn",
    "practice",
    "ladder",
    "revision",
    "readiness",
    "events",
]

__version__ = "0.1.0"
