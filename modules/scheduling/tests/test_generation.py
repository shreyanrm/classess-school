"""From-scratch timetable generation: three named axes, resource scoring, never commits."""

from __future__ import annotations

import pytest

from app.generation import (
    GenerationAxis,
    GenerationInputs,
    TeachingRequirement,
    TimetableGenerator,
    commit_generated,
    score_resource_use,
)
from app.timetable import Period, Slot


INST = "11110000-0000-4000-8000-000000000001"
T_ALPHA = "aaaa0000-0000-4000-8000-000000000001"
T_BETA = "bbbb0000-0000-4000-8000-000000000002"
APPROVER = "dddd0000-0000-4000-8000-000000000009"


def _grid() -> list[Slot]:
    # 5 weekdays x 4 periods = 20 slots.
    return [Slot(w, p) for w in range(5) for p in range(1, 5)]


def _inputs() -> GenerationInputs:
    return GenerationInputs(
        institution_id=INST,
        requirements=[
            TeachingRequirement("r1", "S10A", "math", T_ALPHA, periods_per_week=5),
            TeachingRequirement("r2", "S10A", "sci", T_BETA, periods_per_week=4),
            TeachingRequirement("r3", "S10B", "math", T_ALPHA, periods_per_week=3),
        ],
        slots=_grid(),
        rooms=["R1", "R2", "R3"],
    )


def test_generate_returns_the_three_named_alternatives():
    gen = TimetableGenerator(owner_ref=APPROVER)
    alts = gen.generate(_inputs())
    axes = [a.axis for a in alts]
    assert axes == [
        GenerationAxis.ACADEMIC_BALANCE,
        GenerationAxis.WORKLOAD_BALANCE,
        GenerationAxis.RESOURCE_USE,
    ]
    # Every alternative carries all three scores (the trade-off is explicit).
    for a in alts:
        assert 0.0 <= a.scores.academic_balance <= 1.0
        assert 0.0 <= a.scores.workload_balance <= 1.0
        assert 0.0 <= a.scores.resource_use <= 1.0
        assert len(a.evidence) >= 3  # one line per axis at least.


def test_every_alternative_is_feasible_no_hard_clash():
    gen = TimetableGenerator()
    for a in gen.generate(_inputs()):
        seen_teacher: set = set()
        seen_section: set = set()
        seen_room: set = set()
        for p in a.periods:
            tk = (p.teacher_ref, p.slot)
            sk = (p.section_id, p.slot)
            assert tk not in seen_teacher, "teacher double-booked"
            assert sk not in seen_section, "section double-booked"
            seen_teacher.add(tk)
            seen_section.add(sk)
            if p.room_id is not None:
                rk = (p.room_id, p.slot)
                assert rk not in seen_room, "room double-booked"
                seen_room.add(rk)


def test_full_demand_is_placed_when_grid_is_wide_enough():
    gen = TimetableGenerator()
    for a in gen.generate(_inputs()):
        assert a.fully_placed is True
        assert len(a.periods) == _inputs().total_demand()


def test_resource_axis_packs_rooms_at_least_as_tight_as_others():
    gen = TimetableGenerator()
    alts = {a.axis: a for a in gen.generate(_inputs())}
    res = alts[GenerationAxis.RESOURCE_USE].scores.resource_use
    aca = alts[GenerationAxis.ACADEMIC_BALANCE].scores.resource_use
    assert res >= aca - 1e-9  # resource axis never does worse on its own axis.


def test_resource_score_rewards_tight_packing():
    # One room carrying everything -> perfect utilisation 1.0.
    tight = [Period(f"p{i}", "S", Slot(0, i), "math", T_ALPHA, room_id="R1") for i in range(1, 4)]
    assert score_resource_use(tight, ["R1", "R2"]) == 1.0
    # Spread across rooms each holding one period -> still 1.0 only if equal load;
    # one busy + one idle-but-opened single -> lower.
    loose = [
        Period("p1", "S", Slot(0, 1), "math", T_ALPHA, room_id="R1"),
        Period("p2", "S", Slot(0, 2), "math", T_ALPHA, room_id="R1"),
        Period("p3", "S", Slot(0, 1), "sci", T_BETA, room_id="R2"),
    ]
    # R1 load 2, R2 load 1 -> utilisation 3/(2*2)=0.75.
    assert score_resource_use(loose, ["R1", "R2"]) == 0.75


def test_generation_never_auto_commits():
    gen = TimetableGenerator()
    for a in gen.generate(_inputs()):
        assert a.committed is False
        assert a.is_consequential is True
        assert a.ladder_stage == "execute_with_permission"


def test_commit_requires_human_approval():
    gen = TimetableGenerator()
    best = gen.generate_for_axis(_inputs(), GenerationAxis.RESOURCE_USE)
    with pytest.raises(PermissionError):
        commit_generated(best, approved_by=None)
    live = commit_generated(best, approved_by=APPROVER)
    assert best.committed is True
    assert live.institution_id == INST
    assert len(live.periods) == len(best.periods)


def test_commit_refuses_unplaced_timetable():
    # A grid too small to fit demand leaves requirements unplaced.
    tiny = GenerationInputs(
        institution_id=INST,
        requirements=[TeachingRequirement("r1", "S10A", "math", T_ALPHA, periods_per_week=5)],
        slots=[Slot(0, 1), Slot(0, 2)],  # only 2 slots for 5 periods.
        rooms=["R1"],
    )
    gen = TimetableGenerator()
    g = gen.generate_for_axis(tiny, GenerationAxis.ACADEMIC_BALANCE)
    assert g.fully_placed is False
    with pytest.raises(ValueError):
        commit_generated(g, approved_by=APPROVER)
