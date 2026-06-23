"""Pacing recovery, period swapping, and low-risk automation within policy."""

from __future__ import annotations

from datetime import date

import pytest

from app.pacing import PacingPlan, assess_pacing
from app.recovery import (
    AutomationPolicy,
    PeriodSwap,
    RecoveryContext,
    RecoveryKind,
    apply_swap,
    auto_apply_low_risk,
    evaluate_low_risk,
    propose_period_swap,
    recommend_recovery,
)
from app.timetable import Period, Slot, Timetable


INST = "11110000-0000-4000-8000-000000000001"
T_ALPHA = "aaaa0000-0000-4000-8000-000000000001"
T_BETA = "bbbb0000-0000-4000-8000-000000000002"
APPROVER = "dddd0000-0000-4000-8000-000000000009"


def _behind_status():
    plan = PacingPlan("S10B", "math", planned_periods=40, working_days_total=20, periods_per_working_day=2.0)
    # 20 expected, delivered 14 -> 30% behind.
    return assess_pacing(plan, as_of=date(2026, 6, 15), working_days_elapsed=10, delivered_periods=14)


def _on_track_status():
    plan = PacingPlan("S10B", "math", planned_periods=40, working_days_total=20, periods_per_working_day=2.0)
    return assess_pacing(plan, as_of=date(2026, 6, 15), working_days_elapsed=10, delivered_periods=20)


# -- recommend_recovery -----------------------------------------------------


def test_no_recovery_when_on_track():
    assert recommend_recovery(_on_track_status()) == []


def test_recovery_recommends_add_period_and_reallocate():
    ctx = RecoveryContext(
        free_slots=[Slot(2, 4)],
        ahead_subjects=["sci"],
    )
    actions = recommend_recovery(_behind_status(), ctx, owner_ref=APPROVER)
    kinds = {a.kind for a in actions}
    assert RecoveryKind.ADD_PERIOD in kinds
    assert RecoveryKind.REALLOCATE_SLOT in kinds
    for a in actions:
        assert a.owed_periods > 0
        assert a.is_consequential is True
        assert a.ladder_stage == "execute_with_permission"
        assert a.why and a.consequence_of_applying


def test_revision_block_offered_first_near_assessment():
    ctx = RecoveryContext(free_slots=[Slot(2, 4)], assessment_near=True)
    actions = recommend_recovery(_behind_status(), ctx)
    assert actions[0].kind is RecoveryKind.REVISION_BLOCK


def test_reallocate_is_time_neutral_marking_only_swap_low_risk():
    ctx = RecoveryContext(ahead_subjects=["sci"])
    actions = recommend_recovery(_behind_status(), ctx)
    realloc = next(a for a in actions if a.kind is RecoveryKind.REALLOCATE_SLOT)
    # Reallocate/add/revision change total subject time -> not time-neutral.
    assert realloc.changes_total_teaching_time is True
    assert realloc.confidence_band == "medium"


# -- period swap proposal + apply ------------------------------------------


def _swap_timetable() -> Timetable:
    # Same teacher Alpha teaches S10A math twice on different days; swapping the
    # two periods' slots is a clean rearrangement.
    return Timetable(
        institution_id=INST,
        periods=[
            Period("p1", "S10A", Slot(0, 1), "math", T_ALPHA, room_id="R1"),
            Period("p2", "S10A", Slot(3, 2), "math", T_ALPHA, room_id="R1"),
        ],
    )


def test_propose_swap_rejects_self_and_missing():
    tt = _swap_timetable()
    with pytest.raises(ValueError):
        propose_period_swap(tt, "p1", "p1")
    with pytest.raises(ValueError):
        propose_period_swap(tt, "p1", "nope")


def test_apply_swap_requires_approval_and_exchanges_slots():
    tt = _swap_timetable()
    swap = propose_period_swap(tt, "p1", "p2", owner_ref=APPROVER)
    assert swap.is_consequential is True
    with pytest.raises(PermissionError):
        apply_swap(tt, swap, approved_by=None)
    a, b = apply_swap(tt, swap, approved_by=APPROVER)
    assert a.slot == Slot(3, 2)  # p1 took p2's slot.
    assert b.slot == Slot(0, 1)  # p2 took p1's slot.
    assert tt.by_id("p1").slot == Slot(3, 2)


def test_apply_swap_refuses_when_it_would_clash():
    # Swapping into a slot where the same teacher already teaches another section.
    tt = Timetable(
        institution_id=INST,
        periods=[
            Period("p1", "S10A", Slot(0, 1), "math", T_ALPHA),
            Period("p2", "S10B", Slot(3, 2), "math", T_ALPHA),
            # Alpha is also busy on Mon/1... already p1; create a real clash:
            # another period for Alpha in p2's target slot (Mon/1) belonging to S10C.
            Period("p3", "S10C", Slot(0, 1), "math", T_ALPHA),
        ],
    )
    swap = propose_period_swap(tt, "p2", "p3")
    # p3 already shares Slot(0,1) with p1 (pre-existing), but the swap moves p2
    # INTO Slot(0,1) where p1 (Alpha) sits -> teacher clash on apply.
    with pytest.raises(ValueError):
        apply_swap(tt, swap, approved_by=APPROVER)


# -- low-risk automation within policy -------------------------------------


def test_low_risk_disabled_policy_requires_approval():
    tt = _swap_timetable()
    swap = propose_period_swap(tt, "p1", "p2")
    decision = evaluate_low_risk(tt, swap, AutomationPolicy(enabled=False))
    assert decision.requires_approval is True
    assert decision.auto_apply is False
    assert decision.ladder_stage == "execute_with_permission"


def test_low_risk_enabled_clean_swap_auto_applies():
    tt = _swap_timetable()
    swap = propose_period_swap(tt, "p1", "p2")
    policy = AutomationPolicy(enabled=True, max_teacher_periods_per_day=6)
    decision = evaluate_low_risk(tt, swap, policy)
    assert decision.auto_apply is True
    assert decision.requires_approval is False
    assert decision.ladder_stage == "auto_within_policy"
    a, b = auto_apply_low_risk(tt, swap, policy)
    assert a.slot == Slot(3, 2)


def test_low_risk_blocked_by_exam_blackout():
    tt = _swap_timetable()
    swap = propose_period_swap(tt, "p1", "p2")
    policy = AutomationPolicy(enabled=True, exam_blackout_slots=frozenset({(0, 1)}))
    decision = evaluate_low_risk(tt, swap, policy)
    assert decision.requires_approval is True
    assert any("blackout" in r for r in decision.reasons)


def test_low_risk_blocked_by_teacher_daily_ceiling():
    tt = _swap_timetable()
    swap = propose_period_swap(tt, "p1", "p2")
    policy = AutomationPolicy(enabled=True, max_teacher_periods_per_day=1)
    # After the swap both of Alpha's periods are on different days (load 1 each),
    # so a ceiling of 1 still passes. Force a violation: add a 3rd Alpha period
    # on the day p1 would move TO (weekday 3) so that day reaches load 2.
    tt.periods.append(Period("p3", "S10C", Slot(3, 3), "math", T_ALPHA, room_id="R2"))
    decision = evaluate_low_risk(tt, swap, policy)
    assert decision.requires_approval is True
    assert any("ceiling" in r for r in decision.reasons)


def test_auto_apply_refuses_outside_policy():
    tt = _swap_timetable()
    swap = propose_period_swap(tt, "p1", "p2")
    with pytest.raises(PermissionError):
        auto_apply_low_risk(tt, swap, AutomationPolicy(enabled=False))


def test_decision_flags_are_mutually_exclusive():
    from app.recovery import LowRiskDecision

    with pytest.raises(ValueError):
        LowRiskDecision(auto_apply=True, requires_approval=True)
    with pytest.raises(ValueError):
        LowRiskDecision(auto_apply=False, requires_approval=False)
