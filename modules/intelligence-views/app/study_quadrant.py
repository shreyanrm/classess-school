"""The study quadrant — effort x outcome.

A learner (or cohort, on a topic) is placed on two axes, both resolved through the
governed semantic layer so the numbers agree with every other view:

  - x = ``effort``  (observed, PII-free engagement toward independence),
  - y = ``topic_mastery`` (demonstrated outcome).

The four quadrants name a DIFFERENT response — the point of the quadrant is that
'low outcome' is not one undifferentiated state:

  - high effort, high outcome  -> THRIVING        (sustain, stretch)
  - low effort,  high outcome  -> COASTING        (room to stretch)
  - high effort, low outcome   -> NEEDS_SUPPORT   (working hard, not landing —
                                  the most important quadrant: effort is there,
                                  the approach or a prerequisite is the blocker)
  - low effort,  low outcome   -> NEEDS_REENGAGE  (re-engage before remediate)

Calm, plain-language, never punitive: a placement is a starting point for a human,
never a label on a person. No raw number or formula is surfaced to a
learner/parent — ``plain_language`` is the only learner-facing string.

Deterministic: same inputs, same placement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .semantic_layer import (
    MetricContext,
    MetricValue,
    SemanticLayer,
    build_default_semantic_layer,
)

# The midline separating low/high on each [0,1] axis. A topic at exactly the
# midline is treated as the higher band (benefit of the doubt for the learner).
AXIS_MIDLINE = 0.5


class Quadrant(str, Enum):
    THRIVING = "thriving"
    COASTING = "coasting"
    NEEDS_SUPPORT = "needs_support"
    NEEDS_REENGAGE = "needs_reengage"


_QUADRANT_READING: dict[Quadrant, str] = {
    Quadrant.THRIVING: (
        "Strong effort and strong results. Keep the momentum and offer a stretch."
    ),
    Quadrant.COASTING: (
        "Good results with room to put in more. There is space to stretch toward "
        "harder work."
    ),
    Quadrant.NEEDS_SUPPORT: (
        "Real effort is going in but it is not landing yet. The approach or an "
        "earlier topic is likely the blocker — support, do not push harder."
    ),
    Quadrant.NEEDS_REENGAGE: (
        "Low effort and low results so far. Re-engage first; a fresh, low-stakes "
        "win before any remediation."
    ),
}


def _quadrant(effort: float, outcome: float) -> Quadrant:
    high_effort = effort >= AXIS_MIDLINE
    high_outcome = outcome >= AXIS_MIDLINE
    if high_effort and high_outcome:
        return Quadrant.THRIVING
    if not high_effort and high_outcome:
        return Quadrant.COASTING
    if high_effort and not high_outcome:
        return Quadrant.NEEDS_SUPPORT
    return Quadrant.NEEDS_REENGAGE


@dataclass(frozen=True)
class QuadrantPlacement:
    """One placement on the effort x outcome plane, with explainability.

    ``effort``/``outcome`` are the resolved metric VALUES (internal). The
    learner/parent surface renders ``plain_language`` and the banded axis words —
    never the raw coordinates."""

    label: str  # generic cohort/learner label, never a real name
    topic_id: Any
    quadrant: Quadrant
    effort: float
    outcome: float
    effort_words: str
    outcome_words: str
    plain_language: str
    why_am_i_seeing_this: str

    @property
    def axes(self) -> tuple[float, float]:
        """(x, y) for plotting — internal coordinates only."""
        return (self.effort, self.outcome)


def _placement(
    *,
    label: str,
    topic_id: Any,
    effort_m: MetricValue,
    outcome_m: MetricValue,
) -> QuadrantPlacement:
    q = _quadrant(effort_m.value, outcome_m.value)
    plain = (
        f"{label}: {effort_m.plain_language}, {outcome_m.plain_language}. "
        f"{_QUADRANT_READING[q]}"
    )
    why = (
        "You are seeing this placement because it pairs observed effort with "
        "demonstrated outcome on this topic. Both numbers come from the shared "
        "semantic layer, so they match what other screens show. The placement is "
        "a starting point for a human, never a label on a person."
    )
    return QuadrantPlacement(
        label=label,
        topic_id=topic_id,
        quadrant=q,
        effort=effort_m.value,
        outcome=outcome_m.value,
        effort_words=effort_m.plain_language,
        outcome_words=outcome_m.plain_language,
        plain_language=plain,
        why_am_i_seeing_this=why,
    )


def place_cohort(
    profiles: list[Any],
    *,
    topic_id: Any,
    cohort_label: str = "This cohort",
    effort: dict[Any, float] | None = None,
    layer: SemanticLayer | None = None,
) -> QuadrantPlacement:
    """Place a whole cohort on the quadrant for one topic."""
    layer = layer or build_default_semantic_layer()
    ctx = MetricContext(profiles=profiles, topic_id=topic_id, extra={"effort": effort or {}})
    return _placement(
        label=cohort_label,
        topic_id=topic_id,
        effort_m=layer.compute("effort", ctx),
        outcome_m=layer.compute("topic_mastery", ctx),
    )


def place_learner(
    profiles: list[Any],
    *,
    subject: Any,
    topic_id: Any,
    learner_label: str = "This learner",
    effort: dict[Any, float] | None = None,
    layer: SemanticLayer | None = None,
) -> QuadrantPlacement:
    """Place ONE learner on the quadrant for one topic. Scoped to that learner so
    effort and outcome reflect only their evidence — the same definitions as the
    cohort view."""
    layer = layer or build_default_semantic_layer()
    learner_profiles = [p for p in profiles if p.subject == subject]
    ctx = MetricContext(
        profiles=learner_profiles, topic_id=topic_id, extra={"effort": effort or {}}
    )
    return _placement(
        label=learner_label,
        topic_id=topic_id,
        effort_m=layer.compute("effort", ctx),
        outcome_m=layer.compute("topic_mastery", ctx),
    )


def quadrant_summary(placements: list[QuadrantPlacement]) -> dict[str, int]:
    """Count placements per quadrant — a calm overview, no raw numbers. Keyed by
    the quadrant value for a stable, renderable summary."""
    counts: dict[str, int] = {q.value: 0 for q in Quadrant}
    for p in placements:
        counts[p.quadrant.value] += 1
    return counts
