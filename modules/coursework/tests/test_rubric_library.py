"""The full 13-type rubric library + curriculum alignment + teacher edits."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.contracts import RubricCriterion
from app.rubric import (
    GROUP_PROJECT_DIMENSIONS,
    RUBRIC_TYPE_DOCS,
    RubricType,
    full_library,
    group_project_rubric,
    process_working_rubric,
    rubric_for_type,
    score_response,
)


def test_full_library_has_thirteen_named_types():
    lib = full_library()
    assert len(lib) == 13
    assert set(lib.keys()) == set(RubricType)
    # Every named type carries its type on the rubric.
    for rt, rubric in lib.items():
        assert rubric.rubric_type is rt
        assert rubric.total_max_points > 0
        assert RUBRIC_TYPE_DOCS[rt]


def test_rubric_for_type_round_trips_every_type():
    for rt in RubricType:
        r = rubric_for_type(rt)
        assert r.rubric_type is rt
        assert len(r.criteria) >= 1


def test_process_working_credits_method_with_wrong_final_answer():
    # The dossier example: sound method, wrong final answer => partial credit.
    r = process_working_rubric(max_points=5.0)
    method, steps, final = r.criteria
    awards = {method.criterion_id: method.max_points, steps.criterion_id: steps.max_points, final.criterion_id: 0.0}
    scored = score_response(r, awards)
    assert 0.0 < scored.normalized < 1.0  # partial credit, not zero, not full


def test_rubric_curriculum_alignment_is_copy():
    r = rubric_for_type(RubricType.CONCEPTUAL_UNDERSTANDING)
    assert r.aligned_topic_id is None
    topic = uuid4()
    aligned = r.aligned_to(topic)
    assert aligned.aligned_topic_id == topic
    assert r.aligned_topic_id is None  # original untouched (immutable edit)


def test_teacher_edit_criterion_changes_points_and_text():
    r = rubric_for_type(RubricType.DESCRIPTIVE)
    cid = r.criteria[0].criterion_id
    edited = r.edit_criterion(cid, description="Spot on facts.", max_points=5.0)
    c = edited.criterion(cid)
    assert c.description == "Spot on facts."
    assert c.max_points == 5.0
    # Original rubric unchanged.
    assert r.criterion(cid).max_points != 5.0


def test_teacher_add_and_remove_criterion():
    r = rubric_for_type(RubricType.ORAL)
    extra = RubricCriterion(criterion_id=uuid4(), description="Confidence.", max_points=1.0, weight=0.1)
    bigger = r.with_criterion(extra)
    assert len(bigger.criteria) == len(r.criteria) + 1
    smaller = bigger.without_criterion(extra.criterion_id)
    assert len(smaller.criteria) == len(r.criteria)


def test_cannot_remove_last_criterion():
    r = rubric_for_type(RubricType.CORRECTNESS)
    with pytest.raises(ValueError):
        r.without_criterion(r.criteria[0].criterion_id)


def test_edit_unknown_criterion_raises():
    r = rubric_for_type(RubricType.CODING)
    with pytest.raises(KeyError):
        r.edit_criterion(uuid4(), max_points=2.0)


def test_six_dimension_group_project_rubric():
    r = group_project_rubric()
    assert len(r.criteria) == 6
    assert len(GROUP_PROJECT_DIMENSIONS) == 6
    # Each named dimension appears in a criterion description.
    blob = " ".join(c.description.lower() for c in r.criteria)
    for dim in ("contribution", "collaboration", "communication", "leadership", "quality", "problem"):
        assert dim in blob


def test_originality_rubric_is_separate_from_correctness():
    # Originality is assessed separately from academic correctness — its criteria
    # judge authorship, not whether the answer is right.
    r = rubric_for_type(RubricType.ORIGINALITY)
    blob = " ".join(c.description.lower() for c in r.criteria)
    assert "own words" in blob
    assert "correct" not in blob
