"""Coursework & assessment module (B6).

A capability module over the secure core. The evaluation engine is CORE-grade
(correctness is existential). The package surface:

  - ``assignments`` — create assignments / quick-checks / projects, ontology-mapped.
  - ``papers``      — blueprint-driven paper generation through generate-and-verify.
  - ``evaluation``  — the three-mode evaluation engine (post-submission,
                      scanned-handwriting, preventive-before-submission).
  - ``rubric``      — the rubric library + deterministic scoring.
  - ``originality`` — the originality / similarity check interface.
  - ``events``      — emit submission/score/attempt-evidence events on the
                      contract shapes (independent vs supported flagged).
  - ``contracts``   — pydantic mirrors of the evaluation contract.
  - ``config``      — env-var NAMES only (degrades gracefully with none set).

Import-safe: importing the package, or any submodule, performs no I/O, reads no
secret values, and never requires a live provider.
"""

from __future__ import annotations

from . import (  # noqa: F401
    assignments,
    config,
    contracts,
    evaluation,
    events,
    originality,
    papers,
    rubric,
)

__all__ = [
    "assignments",
    "config",
    "contracts",
    "evaluation",
    "events",
    "originality",
    "papers",
    "rubric",
]
