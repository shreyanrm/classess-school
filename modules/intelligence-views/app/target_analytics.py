"""Target analytics — target vs trajectory.

A target is a human-set goal for a topic (e.g. "this cohort should reach secure
mastery on this topic by the term break"). Target analytics compares that target
against the forecast trajectory (from ``prediction``) and reports the GAP TO
TARGET with full explainability: the evidence the comparison rests on, a
confidence band, the owner, the consequence of ignoring, and the
why-am-i-seeing-this line.

The target is set by a human (it is an input, never invented by the system).
Everything here is advisory and informs a human; nothing acts. The plain-language
reading is the only learner/parent-facing string — never a raw number or formula.

Numbers come through the semantic layer (via ``prediction``), so "mastery" and
"coverage" mean the same here as everywhere. Deterministic and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .prediction import (
    Forecast,
    TARGET_MASTERY,
    TrajectoryDirection,
    forecast_topic,
)
from .semantic_layer import SemanticLayer


class TargetStatus(str, Enum):
    MET_OR_AHEAD = "met_or_ahead"
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    OFF_TRACK = "off_track"


@dataclass(frozen=True)
class Target:
    """A human-set goal. ``target_mastery`` is the desired composite (internal,
    for ranking); ``label`` is the plain-language goal phrasing shown to humans."""

    topic_id: Any
    topic_label: str
    target_mastery: float = TARGET_MASTERY
    due_date: datetime | None = None
    owner_role: str = "coordinator"
    owner_ref: Any | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.target_mastery <= 1.0:
            raise ValueError("target_mastery must be in [0, 1].")


@dataclass(frozen=True)
class TargetAnalysis:
    """Target vs trajectory for one topic, fully explainable.

    ``gap_to_target`` and the raw masteries are internal; the learner/parent-safe
    string is ``plain_language``."""

    topic_id: Any
    topic_label: str
    status: TargetStatus
    target_mastery: float
    current_mastery: float
    projected_mastery: float
    gap_to_target: float
    confidence_band: str
    plain_language: str
    consequence_of_ignoring: str
    why_am_i_seeing_this: str
    owner_role: str
    owner_ref: Any | None
    due_date: datetime | None
    forecast: Forecast
    degraded_reasons: list[str] = field(default_factory=list)


def _status(projected: float, current: float, target: float, direction: TrajectoryDirection) -> TargetStatus:
    if current >= target:
        return TargetStatus.MET_OR_AHEAD
    if projected >= target:
        return TargetStatus.ON_TRACK
    if direction == TrajectoryDirection.BEHIND:
        return TargetStatus.OFF_TRACK
    return TargetStatus.AT_RISK


_STATUS_WORDS: dict[TargetStatus, str] = {
    TargetStatus.MET_OR_AHEAD: "the goal is already met",
    TargetStatus.ON_TRACK: "the goal looks reachable on the current path",
    TargetStatus.AT_RISK: "the goal is at risk without a change",
    TargetStatus.OFF_TRACK: "the goal is unlikely on the current path",
}


def analyze_target(
    profiles: list[Any],
    target: Target,
    *,
    coverage: dict[Any, tuple[float, float]] | None = None,
    layer: SemanticLayer | None = None,
    degraded_reasons: list[str] | None = None,
) -> TargetAnalysis:
    """Compare a human-set target against the forecast trajectory for its topic."""
    fc = forecast_topic(
        profiles,
        topic_id=target.topic_id,
        coverage=coverage,
        layer=layer,
        degraded_reasons=degraded_reasons,
    )
    gap = max(0.0, target.target_mastery - fc.projected_mastery)
    status = _status(fc.projected_mastery, fc.current_mastery, target.target_mastery, fc.direction)

    # The plain reading reuses the forecast's learner-safe phrasing.
    plain = (
        f"Goal for {target.topic_label}: {_STATUS_WORDS[status]}. {fc.plain_language}"
    )

    if status in (TargetStatus.AT_RISK, TargetStatus.OFF_TRACK):
        consequence = (
            f"If the goal for {target.topic_label} is not acted on, the cohort is "
            "likely to reach the due date below the intended level, and dependent "
            "topics built on it will be harder."
        )
    else:
        consequence = (
            f"No action needed on {target.topic_label} for now; keep the current "
            "approach and re-check as fresh evidence arrives."
        )

    why = (
        f"You are seeing this because a human set a goal for {target.topic_label} "
        "and the current trajectory has been compared against it. The numbers come "
        "from the shared semantic layer, so they match the dashboards. This is "
        "advisory; you own the decision."
    )

    return TargetAnalysis(
        topic_id=target.topic_id,
        topic_label=target.topic_label,
        status=status,
        target_mastery=target.target_mastery,
        current_mastery=fc.current_mastery,
        projected_mastery=fc.projected_mastery,
        gap_to_target=gap,
        confidence_band=fc.confidence_band,
        plain_language=plain,
        consequence_of_ignoring=consequence,
        why_am_i_seeing_this=why,
        owner_role=target.owner_role,
        owner_ref=target.owner_ref,
        due_date=target.due_date,
        forecast=fc,
        degraded_reasons=degraded_reasons or [],
    )


def analyze_targets(
    profiles: list[Any],
    targets: list[Target],
    *,
    coverage: dict[Any, tuple[float, float]] | None = None,
    layer: SemanticLayer | None = None,
    degraded_reasons: list[str] | None = None,
) -> list[TargetAnalysis]:
    """Analyze several targets. Sorted most-at-risk first (off-track, then
    at-risk), so a human sees what needs attention at the top."""
    layer = layer  # shared layer keeps every metric one-definition
    results = [
        analyze_target(
            profiles, t, coverage=coverage, layer=layer, degraded_reasons=degraded_reasons
        )
        for t in targets
    ]
    order = {
        TargetStatus.OFF_TRACK: 0,
        TargetStatus.AT_RISK: 1,
        TargetStatus.ON_TRACK: 2,
        TargetStatus.MET_OR_AHEAD: 3,
    }
    results.sort(key=lambda a: (order[a.status], -a.gap_to_target))
    return results
