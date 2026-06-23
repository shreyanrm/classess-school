"""Recommendation builders — turn interpreted signals into well-formed objects.

A builder takes an interpreted signal (e.g. "Class 10-B is weak on Trigonometry
prerequisites") and produces a Recommendation carrying FULL provenance: the
evidence summary, the linked evidence event refs (never an opaque claim), a
confidence band, the owner (role + opaque ref), the consequence of ignoring, the
plain-language why-am-i-seeing-this, the suggested action, and the ladder stage.

The ladder stage is derived from the action's effect via
``permission.classify_action`` so a builder cannot accidentally mint a
consequential recommendation as safe_automatic — classification and the model
validator both refuse it.

CONFIDENTIALITY: builders accept and emit only generic cohort/role labels and
opaque refs. No real names, no codenames, no board lock-in, no emoji, no
exclamation marks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from .models import (
    EvidenceRef,
    LadderStage,
    Recommendation,
    RecommendationConfidenceBand,
    RecommendationOwner,
)
from .permission import ActionDescriptor, LadderPolicy, classify_action

# The ten gap types (mirrors the event contract GapType), used to phrase the
# evidence and the why-line precisely rather than as an opaque claim.
GAP_TYPES = frozenset(
    {
        "prerequisite",
        "conceptual",
        "procedural",
        "application",
        "retention",
        "language",
        "accuracy",
        "speed",
        "confidence",
        "support-dependency",
    }
)


def _band_from_confidence(confidence: float) -> RecommendationConfidenceBand:
    """Map a [0,1] confidence to the three-band scale. Fail toward 'low'."""
    if confidence >= 0.8:
        return RecommendationConfidenceBand.HIGH
    if confidence >= 0.55:
        return RecommendationConfidenceBand.MEDIUM
    return RecommendationConfidenceBand.LOW


def build_recommendation(
    *,
    evidence_summary: str,
    evidence_refs: list[EvidenceRef],
    confidence: float,
    owner_role: str,
    owner_ref: UUID,
    suggested_action: str,
    action: ActionDescriptor,
    consequence_of_ignoring: str,
    why_am_i_seeing_this: str,
    due_date: datetime | None = None,
    policy: LadderPolicy | None = None,
    recommendation_id: UUID | None = None,
) -> Recommendation:
    """Assemble a Recommendation with provenance and a ladder stage derived from
    the action's effect.

    The ladder stage is NEVER passed in by the caller: it is computed from the
    action so a consequential effect is always pinned to execute_with_permission
    and never auto-fires.
    """
    if not evidence_refs:
        raise ValueError("A recommendation must link at least one evidence ref — no opaque claims.")

    ladder = classify_action(action, policy)

    return Recommendation(
        id=recommendation_id or uuid4(),
        evidence_summary=evidence_summary,
        evidence_refs=evidence_refs,
        confidence_band=_band_from_confidence(confidence),
        owner=RecommendationOwner(role=owner_role, ref=owner_ref),
        due_date=due_date,
        consequence_of_ignoring=consequence_of_ignoring,
        why_am_i_seeing_this=why_am_i_seeing_this,
        suggested_action=suggested_action,
        ladder_stage=LadderStage(ladder.stage.value if isinstance(ladder.stage, LadderStage) else ladder.stage),
        is_consequential=ladder.is_consequential,
    )


@dataclass(frozen=True)
class CohortWeaknessSignal:
    """An interpreted signal that a cohort is weak on a topic's gap.

    All labels are generic; ``cohort_label`` is e.g. "Class 10-B", never a real
    section name with PII. ``evidence`` is the linked, attributed evidence.
    """

    cohort_label: str
    topic_label: str
    gap_type: str
    confidence: float
    evidence: list[EvidenceRef]
    owner_role: str
    owner_ref: UUID
    learner_count: int = 0
    due_date: datetime | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.gap_type not in GAP_TYPES:
            raise ValueError(
                f"Unknown gap_type '{self.gap_type}'. Must be one of the ten gap types."
            )
        if not self.evidence:
            raise ValueError("A cohort-weakness signal must carry linked evidence.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1].")


def build_cohort_weakness_recommendation(
    signal: CohortWeaknessSignal,
    *,
    policy: LadderPolicy | None = None,
    recommendation_id: UUID | None = None,
) -> Recommendation:
    """Turn a cohort-weakness signal into a recommendation to PREPARE targeted
    support material.

    The suggested action is to prepare (draft/stage) support — a non-consequential
    preparation step — so it lands at ``prepare`` unless the action itself
    carries a consequential effect. Sending that material to learners/parents
    would be a separate, consequential recommendation that must be approved.
    """
    learners = (
        f" affecting {signal.learner_count} learners"
        if signal.learner_count > 0
        else ""
    )
    evidence_summary = (
        f"{signal.cohort_label} shows a {signal.gap_type} gap on "
        f"{signal.topic_label}{learners}, corroborated by "
        f"{len(signal.evidence)} attributed evidence events."
    )
    why = (
        f"This surfaced because repeated evidence across {signal.cohort_label} "
        f"points to a {signal.gap_type} gap on {signal.topic_label} that is "
        "likely to block upcoming work. You own support for this cohort."
    )
    consequence = (
        f"If left unaddressed, the {signal.gap_type} gap on {signal.topic_label} "
        f"is likely to compound and slow {signal.cohort_label} on dependent topics."
    )
    suggested_action = (
        f"Prepare targeted support material for {signal.cohort_label} on the "
        f"{signal.gap_type} gap in {signal.topic_label}, for your review before use."
    )

    # Preparing material is non-consequential: draft/stage only, internal.
    prepare_action = ActionDescriptor(
        kind="prepare_support_material",
        effect_verb="prepare",
        targets_external=False,
        description=suggested_action,
    )

    return build_recommendation(
        evidence_summary=evidence_summary,
        evidence_refs=list(signal.evidence),
        confidence=signal.confidence,
        owner_role=signal.owner_role,
        owner_ref=signal.owner_ref,
        suggested_action=suggested_action,
        action=prepare_action,
        consequence_of_ignoring=consequence,
        why_am_i_seeing_this=why,
        due_date=signal.due_date,
        policy=policy,
        recommendation_id=recommendation_id,
    )
