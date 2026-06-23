"""Coursework & assessment module (B6).

A capability module over the secure core. The evaluation engine is CORE-grade
(correctness is existential). The package surface:

  - ``assignments`` — create assignments / quick-checks / projects, ontology-mapped.
  - ``papers``      — blueprint-driven paper generation through generate-and-verify.
  - ``evaluation``  — the three-mode evaluation engine (post-submission,
                      scanned-handwriting, preventive-before-submission).
  - ``feedback``    — preventive graduated-hint ladder (never the final answer),
                      "I think I'm right" re-grade requests, confidence check-ins
                      + reflection prompts (self-correction; signals, never marks).
  - ``rubric``      — the full 13-type rubric library + deterministic scoring.
  - ``coverage``    — the blueprint coverage view (completed / untaught /
                      previously-examined) for the paper author.
  - ``groups``      — balanced group composition + project milestones.
  - ``originality`` — originality / similarity + style-shift + explain-or-rewrite.
  - ``reminders``   — risk-based assignment reminders (prepared, human-approved).
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
    coverage,
    evaluation,
    events,
    feedback,
    groups,
    originality,
    papers,
    reminders,
    rubric,
)

__all__ = [
    "assignments",
    "config",
    "contracts",
    "coverage",
    "evaluation",
    "events",
    "feedback",
    "groups",
    "originality",
    "papers",
    "reminders",
    "rubric",
]
