"""Substitution ladder: ranks Level 1-6, never a free period, never auto-assigns."""

from __future__ import annotations

from datetime import date

import pytest

from app.substitution import (
    StaffMember,
    SubLevel,
    SubstitutionLadder,
    VacancyContext,
    assign_substitute,
)


SLOT = "0:1"  # weekday 0, period 1.
APPROVER = "dddd0000-0000-4000-8000-000000000009"


def _vacancy() -> VacancyContext:
    return VacancyContext(
        period_id="p1",
        on_date=date(2026, 6, 22),
        slot_key=SLOT,
        subject_id="math",
        grade_id="g10",
        department_id="dept_math",
        absent_teacher_ref="aaaa0000-0000-4000-8000-000000000001",
    )


def _staff() -> list[StaffMember]:
    return [
        # Level 1: math + grade 10, free.
        StaffMember("s1", "teacher", frozenset({"math"}), "dept_math", frozenset({"g10"}), free_slots=frozenset({SLOT})),
        # Level 2: math but grade 9 only, free.
        StaffMember("s2", "teacher", frozenset({"math"}), "dept_math", frozenset({"g9"}), free_slots=frozenset({SLOT})),
        # Level 3: math, no grade band, free.
        StaffMember("s3", "teacher", frozenset({"math"}), "dept_math", frozenset(), free_slots=frozenset({SLOT})),
        # Level 4: same department, not math, free.
        StaffMember("s4", "teacher", frozenset({"phys"}), "dept_math", frozenset({"g10"}), free_slots=frozenset({SLOT})),
        # Level 5: other department, free.
        StaffMember("s5", "teacher", frozenset({"hist"}), "dept_hum", frozenset({"g10"}), free_slots=frozenset({SLOT})),
        # A duty teacher, free -> enables the Level 6 supervised combine.
        StaffMember("s6", "duty_teacher", frozenset(), "dept_admin", frozenset(), is_duty_teacher=True, free_slots=frozenset({SLOT})),
        # Busy teacher: math+g10 but NOT free -> never offered.
        StaffMember("s7", "teacher", frozenset({"math"}), "dept_math", frozenset({"g10"}), free_slots=frozenset()),
    ]


def test_ladder_ranks_levels_one_through_six_in_order():
    ladder = SubstitutionLadder(owner_ref=APPROVER)
    options = ladder.build_ladder(_vacancy(), _staff())

    levels = [int(o.level) for o in options]
    # Ranked best-first; non-decreasing levels.
    assert levels == sorted(levels)
    # All six levels are represented exactly once given this staff set.
    assert set(levels) == {1, 2, 3, 4, 5, 6}
    # Ranks are 1..N contiguous.
    assert [o.rank for o in options] == list(range(1, len(options) + 1))


def test_busy_teacher_is_never_offered():
    ladder = SubstitutionLadder()
    options = ladder.build_ladder(_vacancy(), _staff())
    offered = {o.staff_ref for o in options}
    assert "s7" not in offered  # busy, even though best-qualified.


def test_no_option_is_ever_a_free_period():
    ladder = SubstitutionLadder()
    options = ladder.build_ladder(_vacancy(), _staff())
    assert options  # coverage is produced.
    for o in options:
        assert o.is_free_period is False
        assert o.is_supervised is True  # every option is supervised.


def test_level_six_supervised_combine_is_the_last_resort_not_a_free_period():
    ladder = SubstitutionLadder()
    # Only a duty teacher is available -> the ONLY option is Level 6 supervised
    # combine. It is still supervised; it is NOT a free period.
    duty_only = [
        StaffMember("s6", "duty_teacher", frozenset(), "dept_admin", frozenset(), is_duty_teacher=True, free_slots=frozenset({SLOT})),
    ]
    options = ladder.build_ladder(_vacancy(), duty_only)
    # A free duty teacher yields a supervised fallback — the Level 6 combine is
    # always present, and every option is supervised and never a free period.
    assert any(o.level is SubLevel.SUPERVISED_COMBINE for o in options)
    for o in options:
        assert o.is_free_period is False
        assert o.is_supervised is True
    # The lowest-preference option offered is the supervised combine.
    assert options[-1].level is SubLevel.SUPERVISED_COMBINE


def test_no_staff_yields_no_options_for_escalation_never_a_free_period():
    ladder = SubstitutionLadder()
    options = ladder.build_ladder(_vacancy(), [])
    # Empty means "escalate", which the caller handles — there is structurally
    # no "free period" option in the list to choose.
    assert options == []


def test_continuity_decreases_down_the_ladder():
    ladder = SubstitutionLadder()
    options = ladder.build_ladder(_vacancy(), _staff())
    continuities = [o.continuity for o in options]
    assert continuities == sorted(continuities, reverse=True)
    assert options[0].confidence_band == "high"  # Level 1 best continuity.


def test_assign_requires_human_approval():
    ladder = SubstitutionLadder(owner_ref=APPROVER)
    options = ladder.build_ladder(_vacancy(), _staff())
    top = options[0]
    with pytest.raises(PermissionError):
        assign_substitute(top, approved_by=None)  # never auto-assigns.
    confirmed = assign_substitute(top, approved_by=APPROVER)
    assert confirmed.staff_ref == top.staff_ref
    assert confirmed.is_free_period is False
