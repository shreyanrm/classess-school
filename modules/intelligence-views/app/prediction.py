"""Trajectory / forecast from mastery + coverage.

A forecast is a PROJECTION over the spine's derived state, not a new judgment. It
combines two governed metrics (both resolved through the semantic layer so the
numbers match every other view): demonstrated ``topic_mastery`` and curriculum
``coverage``. The trajectory is: where is the cohort/learner now, and — holding
the recent rate of demonstrated progress and the remaining coverage — where are
they likely to land by a target date.

DESIGN (explainable intelligence): every forecast carries its evidence (the
metric values it rests on), a confidence band, the assumptions it makes, and a
plain-language reading. It NEVER surfaces a raw probability or formula to a
learner/parent — ``plain_language`` is the only learner-facing string. A forecast
is advisory: it informs a human, it never auto-acts (no consequential effect).

Reproducible: identical inputs (same profiles, same coverage, same asof) yield an
identical forecast — the test asserts this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .semantic_layer import (
    MetricContext,
    SemanticLayer,
    build_default_semantic_layer,
)


class TrajectoryDirection(str, Enum):
    AHEAD = "ahead"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BEHIND = "behind"


@dataclass(frozen=True)
class ForecastInput:
    """Everything the forecast rests on, kept for the evidence trail. Opaque
    refs and PII-free metrics only (INVARIANT 1/2)."""

    topic_id: Any
    current_mastery: float
    coverage: float
    independence: float
    observation_count: int


@dataclass(frozen=True)
class Forecast:
    """A reproducible trajectory forecast with full explainability.

    ``projected_mastery`` and ``confidence`` are internal (ranking / gating); the
    plain-language reading is the only thing a learner/parent surface shows.
    """

    topic_id: Any
    direction: TrajectoryDirection
    current_mastery: float
    projected_mastery: float
    confidence: float
    confidence_band: str
    plain_language: str
    assumptions: list[str]
    evidence: ForecastInput
    why_am_i_seeing_this: str
    # Names of env vars whose absence kept the module on its deterministic path.
    degraded_reasons: list[str] = field(default_factory=list)


# A forecast on thin evidence is low-confidence by construction: a trajectory is
# never asserted from one observation (mirrors the spine's never-from-one-score).
_MIN_OBS_FOR_CONFIDENT_FORECAST = 3

# Target threshold: composite at/above this reads as the cohort being able to do
# the work securely. Mirrors the spine band thresholds (secure >= 0.32).
TARGET_MASTERY = 0.55


def _confidence_band(c: float) -> str:
    if c >= 0.8:
        return "high"
    if c >= 0.55:
        return "medium"
    return "low"


def _project_mastery(current: float, coverage: float, independence: float) -> float:
    """The single forecast definition: blend demonstrated mastery with remaining
    headroom unlocked by coverage, discounted by how independent the work is.

    Intuition: a cohort that is mastering material AND still has planned material
    to deliver has room to climb; one whose progress is mostly support-dependent
    (low independence) climbs more slowly because supported gains do not transfer.
    Bounded to [0,1] and monotone in each input — deterministic.
    """
    headroom = max(0.0, 1.0 - current)
    # Remaining coverage is the engine of further gain; independence governs how
    # much of that gain becomes durable, independent mastery.
    momentum = coverage * (0.4 + 0.6 * independence)
    projected = current + headroom * momentum * 0.5
    return max(0.0, min(1.0, projected))


def _direction(current: float, projected: float, coverage: float) -> TrajectoryDirection:
    if projected >= TARGET_MASTERY and current >= TARGET_MASTERY:
        return TrajectoryDirection.AHEAD
    if projected >= TARGET_MASTERY:
        return TrajectoryDirection.ON_TRACK
    # Below target at the horizon. Distinguish 'at risk' (some room left via
    # coverage) from 'behind' (little coverage left to recover with).
    if coverage < 0.5:
        return TrajectoryDirection.BEHIND
    return TrajectoryDirection.AT_RISK


_DIRECTION_WORDS = {
    TrajectoryDirection.AHEAD: "on track to stay ahead of the target",
    TrajectoryDirection.ON_TRACK: "on track to reach the target",
    TrajectoryDirection.AT_RISK: "at risk of missing the target without a change",
    TrajectoryDirection.BEHIND: "likely to fall short of the target as things stand",
}


def forecast_topic(
    profiles: list[Any],
    *,
    topic_id: Any,
    coverage: dict[Any, tuple[float, float]] | None = None,
    layer: SemanticLayer | None = None,
    degraded_reasons: list[str] | None = None,
) -> Forecast:
    """Forecast a cohort's trajectory on one topic.

    Resolves ``topic_mastery``, ``independence``, and ``coverage`` through the
    semantic layer (so the numbers match every other view) and projects forward.
    """
    layer = layer or build_default_semantic_layer()
    ctx = MetricContext(
        profiles=profiles,
        topic_id=topic_id,
        extra={"coverage": coverage or {}},
    )
    mastery_m = layer.compute("topic_mastery", ctx)
    independence_m = layer.compute("independence", ctx)
    coverage_m = layer.compute("coverage", ctx)

    obs = sum(
        (p.topic(topic_id).mastery.observation_count if p.topic(topic_id) else 0)
        for p in profiles
    )
    current = mastery_m.value
    projected = _project_mastery(current, coverage_m.value, independence_m.value)
    direction = _direction(current, projected, coverage_m.value)

    # Confidence: grows with corroborating observations, discounted when coverage
    # is so low the projection is mostly assumption. Never high on thin evidence.
    obs_factor = 1.0 - 0.6 ** obs if obs > 0 else 0.0
    confidence = max(0.0, min(1.0, obs_factor * (0.5 + 0.5 * coverage_m.value)))
    if obs < _MIN_OBS_FOR_CONFIDENT_FORECAST:
        confidence = min(confidence, 0.5)

    plain = (
        f"This topic is {_DIRECTION_WORDS[direction]}: the cohort is currently "
        f"{mastery_m.plain_language}, with {coverage_m.plain_language}."
    )
    assumptions = [
        "Assumes the recent rate of demonstrated progress continues.",
        "Assumes remaining planned material is delivered.",
        "Supported-only gains are discounted — they do not count as independent mastery.",
    ]
    why = (
        "You are seeing this trajectory because it composes the cohort's "
        "demonstrated mastery and the planned-vs-delivered coverage on this topic "
        "into a forward view. It is advisory and informs your planning; it does "
        "not act on its own."
    )

    return Forecast(
        topic_id=topic_id,
        direction=direction,
        current_mastery=current,
        projected_mastery=projected,
        confidence=confidence,
        confidence_band=_confidence_band(confidence),
        plain_language=plain,
        assumptions=assumptions,
        evidence=ForecastInput(
            topic_id=topic_id,
            current_mastery=current,
            coverage=coverage_m.value,
            independence=independence_m.value,
            observation_count=obs,
        ),
        why_am_i_seeing_this=why,
        degraded_reasons=degraded_reasons or [],
    )


def forecast_learner_topic(
    profiles: list[Any],
    *,
    subject: Any,
    topic_id: Any,
    coverage: dict[Any, tuple[float, float]] | None = None,
    layer: SemanticLayer | None = None,
    degraded_reasons: list[str] | None = None,
) -> Forecast:
    """Forecast ONE learner's trajectory on a topic. Same projection definition,
    scoped to a single learner — the number agrees with the cohort view because
    both go through the semantic layer."""
    learner_profiles = [p for p in profiles if p.subject == subject]
    return forecast_topic(
        learner_profiles,
        topic_id=topic_id,
        coverage=coverage,
        layer=layer,
        degraded_reasons=degraded_reasons,
    )
