"""Surface ``gap.resolved`` — what improved after the last intervention.

The spine intelligence engine emits a ``gap.resolved`` event when a gap that was
once CONFIRMED is no longer confirmed on a fresh recompute (see the spine
``IntelligenceEmitter.emit_for_view``: a resolve is a NEW append-only event,
never a mutation of state). That event is the loop CLOSING: an intervention was
made, fresh evidence arrived, and the gap it targeted has gone.

This module is the VIEW side of that signal. The §08 admin home (`/admin/`) lists
"what improved after the last intervention" as a first-class briefing item, and
the proactive loop's recommendations are balanced by what has already worked. B11
turns the spine's resolved-gap conclusion into a calm, plain-language, fully
evidence-linked IMPROVEMENT item a human reads — never a number, never a claim
without its lineage.

It MINTS nothing consequential and computes no new judgment: a resolution is
derived purely by diffing two governed read views (a ``previous`` and a
``current``), exactly as the spine emitter diffs them, so the surfaced set agrees
with the events the spine emits by construction. Advisory only; nothing acts.

CONFIDENTIALITY: generic cohort/learner labels and opaque refs only. No real
names, no codenames, no board lock-in, no emoji, no exclamation marks.

Deterministic: same (previous, current) pair in, same improvement set out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Reuse the spine EvidenceRef so a resolution's lineage has the SAME shape a
# dashboard alert carries — one provenance vocabulary across every B11 surface.
from .spine_workflow import EvidenceRef

# Plain-language phrasing per gap type — what the cohort can now do that it could
# not before. The gap-type vocabulary is the spine's ten-type set; we phrase the
# improvement, never restate the raw rule.
_RESOLVED_READING: dict[str, str] = {
    "prerequisite": (
        "the earlier topic this was blocked on is no longer holding the work back"
    ),
    "conceptual": "the underlying idea has taken hold",
    "procedural": "the steps are now being carried out reliably",
    "application": "the idea is now transferring to harder, less familiar problems",
    "retention": "what was learned earlier is being recalled again",
    "language": "the comprehension barrier is no longer in the way",
    "accuracy": "the slips and miscalculations have settled down",
    "speed": "the work is now being completed at the pace the context needs",
    "confidence": "the work is now being done with more self-reliance",
    "support-dependency": (
        "the work is now being produced independently, not only with support"
    ),
}


def _resolved_reading(gap_type: str) -> str:
    return _RESOLVED_READING.get(
        gap_type, "this difficulty is no longer showing in the evidence"
    )


@dataclass(frozen=True)
class Improvement:
    """One resolved gap, surfaced for a human — full lineage, plain language.

    Mirrors the spine ``gap.resolved`` conclusion: the named gap that has gone,
    the topic it was on, the plain-language reading of what improved, the linked
    evidence (both the signals that originally confirmed it and the fresh evidence
    that recompute saw), and the explainability line. ``confidence`` is the band
    the gap last carried — internal, for ranking; never surfaced raw."""

    label: str  # generic cohort/learner label, never a real name
    topic_id: Any
    topic_label: str
    gap_type: str
    plain_language: str
    evidence_refs: list[EvidenceRef]
    confidence: float
    why_am_i_seeing_this: str
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.evidence_refs:
            # A resolution without its lineage would be an opaque claim — refuse it,
            # exactly as a dashboard alert refuses to surface without evidence.
            raise ValueError(
                "an improvement must link the evidence the resolution rests on — "
                "no opaque claims."
            )


def _confirmed_by_type(proj: Any) -> dict[str, Any]:
    """Map gap_type -> the confirmed GapResult on a topic projection. Empty when
    the projection is missing or has no confirmed gaps."""
    if proj is None:
        return {}
    return {g.gap_type: g for g in proj.confirmed_gaps}


def _evidence_for_resolution(prev_gap: Any, current_proj: Any) -> list[EvidenceRef]:
    """The lineage of a resolution: the events that originally confirmed the gap
    PLUS the fresh evidence on the topic that the recompute saw it go on. Both
    sides are linked so the surfaced improvement is never an opaque claim."""
    refs: list[EvidenceRef] = []
    seen: set[Any] = set()

    def _add(event_id: Any, summary: str) -> None:
        if event_id in seen:
            return
        seen.add(event_id)
        refs.append(EvidenceRef(event_id=event_id, summary=summary))

    for eid in prev_gap.evidence.evidence_event_ids:
        _add(
            eid,
            "Evidence that originally confirmed this gap (corroborated, not from a "
            "single score).",
        )
    # Fresh evidence the recompute observed the gap go on — the source events on
    # the current topic projection. This is what makes it a resolution, not a
    # disappearance: new evidence arrived and the gap is no longer confirmed.
    if current_proj is not None:
        for eid in current_proj.mastery.evidence_event_ids:
            _add(
                eid,
                "Fresh evidence on this topic since the last view, on which the gap "
                "is no longer confirmed.",
            )
    return refs


def detect_improvements_for_learner(
    previous: Any,
    current: Any,
    *,
    topic_labels: dict[Any, str] | None = None,
    label: str = "This learner",
) -> list[Improvement]:
    """Diff one learner's previous vs current profile and surface resolved gaps.

    A gap is RESOLVED when it was CONFIRMED on a topic in ``previous`` and is no
    longer confirmed on that topic in ``current`` — the exact rule the spine
    emitter uses to emit ``gap.resolved``, so the surfaced set matches the events
    the spine emits. Returns an empty list when nothing resolved.
    """
    topic_labels = topic_labels or {}
    improvements: list[Improvement] = []

    for topic_id, prev_proj in previous.topics.items():
        confirmed_before = _confirmed_by_type(prev_proj)
        if not confirmed_before:
            continue
        current_proj = current.topic(topic_id)
        confirmed_now = _confirmed_by_type(current_proj)
        for gap_type in sorted(confirmed_before.keys() - confirmed_now.keys()):
            prev_gap = confirmed_before[gap_type]
            topic_label = topic_labels.get(topic_id, "this topic")
            plain = (
                f"{label}: on {topic_label}, {_resolved_reading(gap_type)}. The "
                f"{gap_type} difficulty seen before is no longer showing in the "
                "evidence."
            )
            why = (
                "You are seeing this because a difficulty that was confirmed before "
                "is no longer confirmed on fresh evidence — the loop closing on a "
                f"{gap_type} gap on {topic_label}. It is a read of what improved, "
                "not an action."
            )
            improvements.append(
                Improvement(
                    label=label,
                    topic_id=topic_id,
                    topic_label=topic_label,
                    gap_type=gap_type,
                    plain_language=plain,
                    evidence_refs=_evidence_for_resolution(prev_gap, current_proj),
                    confidence=prev_gap.evidence.confidence,
                    why_am_i_seeing_this=why,
                    resolved_at=current.computed_at,
                )
            )
    return improvements


@dataclass(frozen=True)
class CohortImprovement:
    """A resolved gap rolled up across a cohort on one topic — the briefing-level
    "what improved after the last intervention" item. Carries the count of
    learners it resolved for and the merged lineage."""

    topic_id: Any
    topic_label: str
    gap_type: str
    learner_count: int
    plain_language: str
    evidence_refs: list[EvidenceRef]
    why_am_i_seeing_this: str
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.evidence_refs:
            raise ValueError(
                "a cohort improvement must link the evidence it rests on — no "
                "opaque claims."
            )


def detect_cohort_improvements(
    previous: list[Any],
    current: list[Any],
    *,
    cohort_label: str = "This cohort",
    topic_labels: dict[Any, str] | None = None,
) -> list[CohortImprovement]:
    """Roll up resolved gaps across a cohort: ``previous`` and ``current`` are the
    per-learner profile lists from two recomputes (paired by ``subject``).

    For each (topic, gap_type) that resolved for one or more learners, produce one
    briefing item carrying the learner count and the merged, de-duplicated
    lineage. Ranked most-learners-helped first (a stable, deterministic order), so
    the home briefing leads with the intervention that improved the most learners.
    """
    topic_labels = topic_labels or {}
    prev_by_subject = {p.subject: p for p in previous}

    # (topic_id, gap_type) -> aggregated state.
    agg: dict[tuple[Any, str], dict[str, Any]] = {}
    for cur in current:
        prev = prev_by_subject.get(cur.subject)
        if prev is None:
            continue
        for imp in detect_improvements_for_learner(
            prev, cur, topic_labels=topic_labels, label="A learner"
        ):
            key = (imp.topic_id, imp.gap_type)
            slot = agg.setdefault(
                key,
                {
                    "topic_label": imp.topic_label,
                    "count": 0,
                    "refs": [],
                    "seen": set(),
                    "resolved_at": imp.resolved_at,
                },
            )
            slot["count"] += 1
            for ref in imp.evidence_refs:
                if ref.event_id in slot["seen"]:
                    continue
                slot["seen"].add(ref.event_id)
                slot["refs"].append(ref)

    out: list[CohortImprovement] = []
    for (topic_id, gap_type), slot in agg.items():
        topic_label = slot["topic_label"]
        learners = (
            f"{slot['count']} learners" if slot["count"] != 1 else "one learner"
        )
        plain = (
            f"{cohort_label}: on {topic_label}, {_resolved_reading(gap_type)} for "
            f"{learners}. The {gap_type} difficulty seen before is no longer "
            "showing in their evidence."
        )
        why = (
            "You are seeing this because a difficulty confirmed across the cohort "
            "before is no longer confirmed on fresh evidence — the loop closing on "
            f"a {gap_type} gap on {topic_label}. It is a read of what an "
            "intervention improved, not an action."
        )
        out.append(
            CohortImprovement(
                topic_id=topic_id,
                topic_label=topic_label,
                gap_type=gap_type,
                learner_count=slot["count"],
                plain_language=plain,
                evidence_refs=list(slot["refs"]),
                why_am_i_seeing_this=why,
                resolved_at=slot["resolved_at"],
            )
        )
    # Most-learners-helped first; then topic id and gap type for a stable order.
    out.sort(key=lambda c: (-c.learner_count, str(c.topic_id), c.gap_type))
    return out


__all__ = [
    "Improvement",
    "CohortImprovement",
    "detect_improvements_for_learner",
    "detect_cohort_improvements",
]
