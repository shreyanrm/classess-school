"""Timetable solver: scored alternatives, rule classification, never commits."""

from __future__ import annotations

from datetime import date

import pytest

from app.timetable import (
    Candidate,
    Disruption,
    Period,
    RuleClass,
    ScoredAlternative,
    Slot,
    Timetable,
    TimetableSolver,
    apply_change,
)


INST = "11110000-0000-4000-8000-000000000001"
T_ALPHA = "aaaa0000-0000-4000-8000-000000000001"
T_BETA = "bbbb0000-0000-4000-8000-000000000002"
T_GAMMA = "cccc0000-0000-4000-8000-000000000003"
APPROVER = "dddd0000-0000-4000-8000-000000000009"


def _timetable() -> Timetable:
    # Section S10B, Monday: period 1 with teacher Alpha in room R1.
    # Teacher Beta is also teaching in slot Mon/1 (another section) -> busy.
    return Timetable(
        institution_id=INST,
        periods=[
            Period("p1", "S10B", Slot(0, 1), "math", T_ALPHA, room_id="R1"),
            Period("p2", "S10A", Slot(0, 1), "sci", T_BETA, room_id="R2"),
        ],
    )


def _disruption() -> Disruption:
    return Disruption(
        kind="teacher_absent",
        on_date=date(2026, 6, 22),
        affected_period_id="p1",
        absent_teacher_ref=T_ALPHA,
    )


def test_rules_are_classified_hard_soft_contextual():
    solver = TimetableSolver()
    by_class = solver.rules_by_class()
    assert by_class[RuleClass.HARD]  # hard rules exist
    assert by_class[RuleClass.SOFT]  # soft rules exist
    assert by_class[RuleClass.CONTEXTUAL]  # contextual rules exist
    # No rule is in more than one class.
    all_ids = [rid for ids in by_class.values() for rid in ids]
    assert len(all_ids) == len(set(all_ids))


def test_solver_returns_scored_alternatives_and_never_commits():
    solver = TimetableSolver()
    tt = _timetable()
    candidates = [
        Candidate("c-free", "p1", new_teacher_ref=T_GAMMA),  # Gamma is free.
        Candidate("c-busy", "p1", new_teacher_ref=T_BETA),  # Beta clashes (Mon/1).
    ]
    result = solver.solve(candidates, tt, _disruption(), owner_ref=APPROVER, top_n=3)

    assert result.committed is False  # the solver NEVER commits.
    assert len(result.alternatives) == 2
    for alt in result.alternatives:
        assert isinstance(alt, ScoredAlternative)
        assert alt.is_consequential is True
        assert alt.ladder_stage == "execute_with_permission"
        assert 0.0 <= alt.score <= 1.0
        assert alt.evidence  # plain-language evidence is always present.
        assert alt.why and alt.consequence_of_applying


def test_hard_rule_breach_disqualifies_and_ranks_below_feasible():
    solver = TimetableSolver()
    tt = _timetable()
    candidates = [
        Candidate("c-busy", "p1", new_teacher_ref=T_BETA),  # hard clash.
        Candidate("c-free", "p1", new_teacher_ref=T_GAMMA),  # feasible.
    ]
    result = solver.solve(candidates, tt, _disruption(), owner_ref=APPROVER)
    # Feasible one ranks first regardless of input order.
    assert result.alternatives[0].candidate.candidate_id == "c-free"
    assert result.alternatives[0].feasible is True
    # The clashing one is infeasible, scored 0, low confidence.
    busy = next(a for a in result.alternatives if a.candidate.candidate_id == "c-busy")
    assert busy.feasible is False
    assert busy.score == 0.0
    assert busy.confidence_band == "low"
    assert result.best is result.alternatives[0]


def test_contextual_rule_only_applies_to_its_situation():
    solver = TimetableSolver()
    tt = _timetable()
    # Room-loss disruption with a room move (no teacher change) -> the
    # substitute-expertise contextual rule should NOT apply.
    room_disruption = Disruption(
        kind="room_lost", on_date=date(2026, 6, 22), affected_period_id="p1", lost_room_id="R1"
    )
    alt = solver.score_candidate(
        Candidate("c-room", "p1", new_room_id="R3"),
        tt,
        room_disruption,
        owner_ref=APPROVER,
    )
    rule_ids = {r.rule_id for r in alt.rule_results}
    assert "substitute_subject_expertise" not in rule_ids  # inapplicable here.

    # In a teacher-absent fill, the contextual rule DOES apply.
    teacher_alt = solver.score_candidate(
        Candidate("c-fill", "p1", new_teacher_ref=T_GAMMA),
        tt,
        _disruption(),
        owner_ref=APPROVER,
    )
    rule_ids2 = {r.rule_id for r in teacher_alt.rule_results}
    assert "substitute_subject_expertise" in rule_ids2


def test_apply_change_requires_human_approval():
    solver = TimetableSolver()
    tt = _timetable()
    alt = solver.score_candidate(
        Candidate("c-free", "p1", new_teacher_ref=T_GAMMA), tt, _disruption(), owner_ref=APPROVER
    )
    # Without an approver, applying is refused (permission ladder, INVARIANT 8).
    with pytest.raises(PermissionError):
        apply_change(tt, alt, approved_by=None)

    # With a human approver, the change applies and the period is updated.
    updated = apply_change(tt, alt, approved_by=APPROVER)
    assert updated.teacher_ref == T_GAMMA
    assert tt.by_id("p1").teacher_ref == T_GAMMA


def test_apply_change_refuses_infeasible_alternative():
    solver = TimetableSolver()
    tt = _timetable()
    alt = solver.score_candidate(
        Candidate("c-busy", "p1", new_teacher_ref=T_BETA), tt, _disruption(), owner_ref=APPROVER
    )
    assert alt.feasible is False
    with pytest.raises(ValueError):
        apply_change(tt, alt, approved_by=APPROVER)
