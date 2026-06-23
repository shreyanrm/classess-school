"""Assignments + rubric library/scoring tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.assignments import (
    AssignmentItem,
    AssignmentKind,
    OntologyRef,
    Verification,
    create_assignment,
    quick_check,
    project,
)
from app.rubric import (
    get_rubric,
    library,
    partial_credit_rubric,
    score_response,
)


def _ont() -> OntologyRef:
    return OntologyRef(topic_id=uuid4(), outcome_id=uuid4())


def test_create_assignment_maps_ontology():
    a = create_assignment(
        institution_id=uuid4(),
        created_by=uuid4(),
        kind=AssignmentKind.ASSIGNMENT,
        title="Linear equations homework",
        ontology=_ont(),
    )
    assert a.kind is AssignmentKind.ASSIGNMENT
    assert a.assessed_topic_ids  # at least the primary topic


def test_quick_check_caps_items():
    items = [
        AssignmentItem(question_ref=uuid4(), ontology=_ont(), prompt=f"Q{i}")
        for i in range(11)
    ]
    with pytest.raises(Exception):
        quick_check(
            institution_id=uuid4(),
            created_by=uuid4(),
            title="too long",
            ontology=_ont(),
            items=items,
        )


def test_ai_generated_item_must_be_verified():
    # An AI-generated item with no verification is rejected.
    with pytest.raises(Exception):
        AssignmentItem(
            question_ref=uuid4(),
            ontology=_ont(),
            prompt="2+2?",
            ai_generated=True,
        )
    # A failed verification is also rejected (unverified content never served).
    with pytest.raises(Exception):
        AssignmentItem(
            question_ref=uuid4(),
            ontology=_ont(),
            prompt="2+2?",
            ai_generated=True,
            verification=Verification(status="failed", confidence=0.2, gate_threshold=0.85),
        )
    # A passing verification is accepted.
    ok = AssignmentItem(
        question_ref=uuid4(),
        ontology=_ont(),
        prompt="2+2?",
        ai_generated=True,
        verification=Verification(status="passed", confidence=0.99, gate_threshold=0.85),
    )
    assert ok.verification.served


def test_project_total_points():
    items = [
        AssignmentItem(question_ref=uuid4(), ontology=_ont(), prompt="part", max_points=5.0),
        AssignmentItem(question_ref=uuid4(), ontology=_ont(), prompt="part", max_points=3.0),
    ]
    p = project(
        institution_id=uuid4(),
        created_by=uuid4(),
        title="Bridge model",
        ontology=_ont(),
        items=items,
    )
    assert p.total_points == 8.0


def test_library_has_all_rubrics():
    lib = library()
    assert set(lib) == {"binary", "partial_credit", "short_answer", "extended_response", "project"}


def test_partial_credit_scoring_is_deterministic():
    r = partial_credit_rubric(max_points=10.0)
    method, answer = r.criteria[0].criterion_id, r.criteria[1].criterion_id
    # Correct method, wrong final answer => method credit only.
    scored = score_response(r, {method: 6.0, answer: 0.0})
    assert scored.points_awarded == 6.0
    assert abs(scored.normalized - 0.6) < 1e-9
    # Same input, same output (deterministic).
    again = score_response(r, {method: 6.0, answer: 0.0})
    assert again.points_awarded == scored.points_awarded


def test_score_clamps_over_award():
    r = get_rubric("binary")
    cid = r.criteria[0].criterion_id
    scored = score_response(r, {cid: 99.0})  # over-award clamps to max 1.0
    assert scored.points_awarded == 1.0
    assert scored.normalized == 1.0
