"""Development plans (private, longitudinal) + de-identified leadership aggregate.

These guard the two deepenings of B10 the spec calls for: a teacher's own
development plan built from their signals over time, and an aggregate that may
reach leadership only de-identified, above a k-anonymity floor, and only after
coaching has reached the teachers. Never a ranking, never a per-teacher view.
"""

from __future__ import annotations

import pytest

from app.coaching import CoachingSignal
from app.growth_plan import (
    DevelopmentPlan,
    LeadershipAggregate,
    PerTeacherLeadershipViewError,
    TRAJECTORY_IMPROVING,
    TRAJECTORY_SLIPPING,
    TRAJECTORY_STEADY,
    TRAJECTORY_TOO_LITTLE_DATA,
    build_development_plan,
    build_leadership_aggregate,
    guard_no_employment_use,
    refuse_per_teacher_leadership_view,
)

TEACHER = "tttt0000-0000-4000-8000-000000000001"
OTHER = "tttt0000-0000-4000-8000-0000000000ff"
CONSENT = "cccc0000-0000-4000-8000-000000000007"


def _sig(dimension, direction, lesson):
    return CoachingSignal(
        teacher_ref=TEACHER, lesson_id=lesson, dimension=dimension,
        direction=direction, reading="r", suggested_next_step="s",
        evidence="e", confidence="medium",
    )


def _improving_wait_time():
    # growth_area -> neutral -> strength across three lessons: improving.
    return [
        _sig("wait_time", "growth_area", "l1"),
        _sig("wait_time", "neutral", "l2"),
        _sig("wait_time", "strength", "l3"),
    ]


def _slipping_talk():
    return [
        _sig("talk_ratio", "strength", "l1"),
        _sig("talk_ratio", "neutral", "l2"),
        _sig("talk_ratio", "growth_area", "l3"),
    ]


# ---- development plan -------------------------------------------------------


def test_plan_is_private_and_teacher_first():
    plan = build_development_plan(teacher_ref=TEACHER, signals=_improving_wait_time())
    assert plan.private is True
    assert plan.visibility == "teacher_first"
    assert "private" in plan.why_am_i_seeing_this().lower()


def test_plan_cannot_be_constructed_public():
    with pytest.raises(ValueError):
        DevelopmentPlan(teacher_ref=TEACHER, lessons_observed=1, private=False)
    with pytest.raises(ValueError):
        DevelopmentPlan(teacher_ref=TEACHER, lessons_observed=1, visibility="public")


def test_trajectory_reads_improving_steady_slipping_and_too_little_data():
    improving = build_development_plan(
        teacher_ref=TEACHER, signals=_improving_wait_time()
    )
    assert improving.trajectories[0].trajectory == TRAJECTORY_IMPROVING

    slipping = build_development_plan(teacher_ref=TEACHER, signals=_slipping_talk())
    assert slipping.trajectories[0].trajectory == TRAJECTORY_SLIPPING

    steady = build_development_plan(
        teacher_ref=TEACHER,
        signals=[_sig("equity_of_voice", "neutral", f"l{i}") for i in range(4)],
    )
    assert steady.trajectories[0].trajectory == TRAJECTORY_STEADY

    thin = build_development_plan(
        teacher_ref=TEACHER, signals=[_sig("talk_ratio", "strength", "l1")]
    )
    assert thin.trajectories[0].trajectory == TRAJECTORY_TOO_LITTLE_DATA


def test_focus_areas_prioritise_slipping_then_current_growth():
    signals = _slipping_talk() + _improving_wait_time()
    signals.append(_sig("questioning_quality", "growth_area", "l9"))
    plan = build_development_plan(teacher_ref=TEACHER, signals=signals)
    focus_dims = [t.dimension for t in plan.focus_areas]
    # The slipping dimension comes first; improving wait_time is NOT a focus.
    assert focus_dims[0] == "talk_ratio"
    assert "wait_time" not in focus_dims
    assert "questioning_quality" in focus_dims


def test_plan_is_deterministic_and_ordered():
    a = build_development_plan(teacher_ref=TEACHER, signals=_improving_wait_time())
    b = build_development_plan(teacher_ref=TEACHER, signals=_improving_wait_time())
    assert [t.dimension for t in a.trajectories] == [t.dimension for t in b.trajectories]


def test_plan_counts_distinct_lessons():
    plan = build_development_plan(teacher_ref=TEACHER, signals=_improving_wait_time())
    assert plan.lessons_observed == 3


def test_plan_never_mixes_teachers():
    signals = _improving_wait_time() + [
        CoachingSignal(
            teacher_ref=OTHER, lesson_id="lx", dimension="talk_ratio",
            direction="strength", reading="r", suggested_next_step="s",
            evidence="e", confidence="high",
        )
    ]
    with pytest.raises(ValueError):
        build_development_plan(teacher_ref=TEACHER, signals=signals)


def test_plan_exposes_no_rank_rating_or_score():
    plan = build_development_plan(teacher_ref=TEACHER, signals=_improving_wait_time())
    assert not hasattr(plan, "rank")
    assert not hasattr(plan, "rating")
    assert not hasattr(plan, "score")


# ---- leadership aggregate (de-identified, k-anonymous, coaching-first) ------


def _surfaced_plan(teacher_ref, signals):
    plan = build_development_plan(teacher_ref=teacher_ref, signals=signals)
    plan.surfaced_to_teacher = True
    return plan


def _cohort(n, *, surfaced=True):
    plans = []
    for i in range(n):
        ref = f"tttt0000-0000-4000-8000-0000000000{i:02d}"
        sigs = [
            CoachingSignal(
                teacher_ref=ref, lesson_id=f"l{j}", dimension="wait_time",
                direction="growth_area", reading="r", suggested_next_step="s",
                evidence="e", confidence="medium",
            )
            for j in range(3)
        ]
        plan = build_development_plan(teacher_ref=ref, signals=sigs)
        plan.surfaced_to_teacher = surfaced
        plans.append(plan)
    return plans


def test_aggregate_is_de_identified_no_teacher_refs():
    agg = build_leadership_aggregate(_cohort(6))
    assert agg.cohort_size == 6
    # No teacher identity anywhere — only dimension->count distributions.
    blob = repr(agg)
    assert "tttt0000" not in blob
    assert isinstance(agg.focus_area_counts, dict)
    for value in agg.focus_area_counts.values():
        assert isinstance(value, int)


def test_aggregate_refuses_below_k_anonymity_floor():
    # Four teachers is below the default floor of five -> refused.
    with pytest.raises(PerTeacherLeadershipViewError):
        build_leadership_aggregate(_cohort(4))


def test_aggregate_counts_only_plans_surfaced_to_teacher_first():
    # Plans not yet shown to their teachers do not count toward the aggregate,
    # so leadership never sees a shape ahead of the teachers.
    not_surfaced = _cohort(6, surfaced=False)
    with pytest.raises(PerTeacherLeadershipViewError):
        build_leadership_aggregate(not_surfaced)


def test_aggregate_proportion_focus_and_shape():
    agg = build_leadership_aggregate(_cohort(6))
    # All six have wait_time as a focus area -> proportion 1.0.
    assert agg.proportion_focus("wait_time") == 1.0
    assert agg.focus_area_counts.get("wait_time") == 6
    assert "leadership" in agg.why_am_i_seeing_this().lower() or \
           "school" in agg.why_am_i_seeing_this().lower()


def test_one_teacher_cannot_dominate_distribution():
    # A teacher with many lessons still counts once per dimension (presence).
    many = [
        CoachingSignal(
            teacher_ref=TEACHER, lesson_id=f"l{j}", dimension="wait_time",
            direction="growth_area", reading="r", suggested_next_step="s",
            evidence="e", confidence="medium",
        )
        for j in range(20)
    ]
    heavy = _surfaced_plan(TEACHER, many)
    cohort = _cohort(5) + [heavy]
    agg = build_leadership_aggregate(cohort)
    # 6 teachers, each contributes at most 1 to wait_time despite 20 lessons.
    assert agg.focus_area_counts["wait_time"] == 6


# ---- refusals ----------------------------------------------------------------


def test_per_teacher_leadership_view_always_refuses():
    with pytest.raises(PerTeacherLeadershipViewError):
        refuse_per_teacher_leadership_view(teacher=TEACHER, requested_by="leadership")


def test_no_employment_use_guard_refuses():
    from app.coaching import EmploymentDecisionError

    with pytest.raises(EmploymentDecisionError):
        guard_no_employment_use(plan=TEACHER, action="renew")
