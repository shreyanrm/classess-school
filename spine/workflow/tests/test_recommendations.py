"""Recommendation-builder tests: full provenance, correct ladder stage, and the
model-level refusal of a consequential safe_automatic.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import (
    EvidenceRef,
    LadderStage,
    Recommendation,
    RecommendationConfidenceBand,
)
from app.permission import ActionDescriptor
from app.recommendations import (
    CohortWeaknessSignal,
    build_cohort_weakness_recommendation,
    build_recommendation,
)


def _evidence(n: int = 2) -> list[EvidenceRef]:
    return [EvidenceRef(event_id=uuid4(), summary=f"low score on item {i}") for i in range(n)]


def test_cohort_weakness_recommendation_carries_full_provenance():
    owner = uuid4()
    signal = CohortWeaknessSignal(
        cohort_label="Class 10-B",
        topic_label="Trigonometry",
        gap_type="prerequisite",
        confidence=0.82,
        evidence=_evidence(3),
        owner_role="teacher",
        owner_ref=owner,
        learner_count=18,
    )
    rec = build_cohort_weakness_recommendation(signal)

    # Full provenance present.
    assert rec.evidence_summary
    assert len(rec.evidence_refs) == 3
    assert rec.confidence_band == RecommendationConfidenceBand.HIGH.value
    assert rec.owner.role == "teacher"
    assert rec.owner.ref == owner
    assert rec.consequence_of_ignoring
    assert rec.why_am_i_seeing_this
    assert rec.suggested_action
    # Preparing material is non-consequential -> not pinned to execute_with_permission.
    assert rec.is_consequential is False
    assert rec.ladder_stage in {LadderStage.RECOMMEND.value, LadderStage.SAFE_AUTOMATIC.value, LadderStage.PREPARE.value}
    # Confidentiality: generic labels only, no PII in the prose.
    assert "Class 10-B" in rec.evidence_summary
    assert "Trigonometry" in rec.why_am_i_seeing_this


def test_consequential_action_builds_at_execute_with_permission():
    rec = build_recommendation(
        evidence_summary="Cohort report ready to publish to parents.",
        evidence_refs=_evidence(2),
        confidence=0.9,
        owner_role="coordinator",
        owner_ref=uuid4(),
        suggested_action="Publish the cohort report to parents.",
        action=ActionDescriptor(kind="publish_report", effect_verb="publish", targets_external=True),
        consequence_of_ignoring="Parents lack a timely view of progress.",
        why_am_i_seeing_this="A cohort report is prepared and awaiting your approval to publish.",
    )
    assert rec.is_consequential is True
    assert rec.ladder_stage == LadderStage.EXECUTE_WITH_PERMISSION.value


def test_model_refuses_consequential_safe_automatic():
    with pytest.raises(ValidationError):
        Recommendation(
            id=uuid4(),
            evidence_summary="x",
            evidence_refs=_evidence(1),
            confidence_band=RecommendationConfidenceBand.HIGH,
            owner={"role": "teacher", "ref": uuid4()},
            consequence_of_ignoring="y",
            why_am_i_seeing_this="z",
            suggested_action="send it",
            ladder_stage=LadderStage.SAFE_AUTOMATIC,
            is_consequential=True,
        )


def test_unknown_gap_type_rejected():
    with pytest.raises(ValueError):
        CohortWeaknessSignal(
            cohort_label="Class 9-A",
            topic_label="Fractions",
            gap_type="not-a-real-gap",
            confidence=0.6,
            evidence=_evidence(2),
            owner_role="teacher",
            owner_ref=uuid4(),
        )


def test_builder_requires_evidence():
    with pytest.raises(ValueError):
        build_recommendation(
            evidence_summary="x",
            evidence_refs=[],
            confidence=0.7,
            owner_role="teacher",
            owner_ref=uuid4(),
            suggested_action="do",
            action=ActionDescriptor(kind="k", effect_verb="compute"),
            consequence_of_ignoring="y",
            why_am_i_seeing_this="z",
        )


def test_confidence_bands():
    args = dict(
        evidence_refs=_evidence(2),
        owner_role="teacher",
        owner_ref=uuid4(),
        suggested_action="do",
        action=ActionDescriptor(kind="k", effect_verb="compute"),
        consequence_of_ignoring="y",
        why_am_i_seeing_this="z",
        evidence_summary="s",
    )
    assert build_recommendation(confidence=0.9, **args).confidence_band == "high"
    assert build_recommendation(confidence=0.6, **args).confidence_band == "medium"
    assert build_recommendation(confidence=0.2, **args).confidence_band == "low"
