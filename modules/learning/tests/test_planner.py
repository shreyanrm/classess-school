"""The d13 exam-date revision planner + time-left achievability."""

from __future__ import annotations

from datetime import date

import pytest

from learning import planner
from learning.planner import (
    AvailableTime,
    ExamScope,
    PlannerTopic,
    achievable_forecast,
    build_plan,
    replan_after_missed,
)

ASOF = date(2026, 6, 1)
EXAM = date(2026, 6, 21)   # 20 study days available


def _topic(tid, *, weight=1.0, readiness=0.3, evidence=True, due=False, gaps=(), prereqs=(), base=40):
    return PlannerTopic(
        topic_id=tid, weight=weight, readiness=readiness, has_evidence=evidence,
        revision_due=due, confirmed_gap_types=gaps, prerequisites=prereqs, base_minutes=base,
    )


# --- core plan -------------------------------------------------------------
def test_plan_fits_when_time_is_ample():
    topics = [_topic("a", readiness=0.6), _topic("b", readiness=0.7)]
    plan = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(daily_minutes=120), asof=ASOF)
    assert plan.fits
    assert plan.days_available == 20
    assert plan.sessions


def test_weak_prerequisite_is_scheduled_before_its_dependent():
    # "b" depends on "a"; even though both are weak, a (the foundation) comes first.
    topics = [
        _topic("b", readiness=0.3, prereqs=("a",)),
        _topic("a", readiness=0.3),
    ]
    plan = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(daily_minutes=120), asof=ASOF)
    first_day_a = min(s.day for s in plan.sessions if s.topic_id == "a")
    first_day_b = min(s.day for s in plan.sessions if s.topic_id == "b")
    assert first_day_a <= first_day_b
    rank_a = min(s.priority_rank for s in plan.sessions if s.topic_id == "a")
    rank_b = min(s.priority_rank for s in plan.sessions if s.topic_id == "b")
    assert rank_a < rank_b


def test_no_evidence_topic_treated_as_weak_and_scheduled():
    topics = [_topic("a", readiness=0.9), _topic("b", evidence=False, readiness=0.0)]
    plan = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(daily_minutes=120), asof=ASOF)
    assert any(s.topic_id == "b" for s in plan.sessions)


def test_daily_load_never_exceeds_capacity_reducing_stress():
    topics = [_topic(f"t{i}", readiness=0.1, base=60) for i in range(8)]
    cap = 90
    plan = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(daily_minutes=cap), asof=ASOF)
    by_day = plan.sessions_by_day
    for day, sess in by_day.items():
        assert sum(s.minutes for s in sess) <= cap


def test_does_not_overpromise_when_time_is_short():
    # Many weak heavy topics, almost no time: it must not claim everything fits.
    topics = [_topic(f"t{i}", readiness=0.0, evidence=False, base=60) for i in range(10)]
    short_exam = date(2026, 6, 3)  # only 2 study days
    plan = build_plan(exam_date=short_exam, topics=topics, available=AvailableTime(daily_minutes=30), asof=ASOF)
    assert plan.fits is False
    assert plan.deferred_topics  # honest about what did not fit


def test_blackout_days_are_not_scheduled():
    blackout = frozenset({date(2026, 6, 7), date(2026, 6, 8)})
    topics = [_topic("a", readiness=0.2, base=40)]
    plan = build_plan(
        exam_date=EXAM, topics=topics,
        available=AvailableTime(daily_minutes=30, blackout_days=blackout), asof=ASOF,
    )
    assert all(s.day not in blackout for s in plan.sessions)


def test_no_time_left_is_handled_gracefully():
    plan = build_plan(exam_date=ASOF, topics=[_topic("a")], available=AvailableTime(), asof=ASOF)
    assert plan.days_available == 0 and plan.fits is False
    assert "no study time" in plan.plain_language


# --- scopes ----------------------------------------------------------------
def test_competitive_scope_pushes_prerequisites_harder():
    topics = [
        _topic("dependent", readiness=0.5, weight=2.0),
        _topic("foundation", readiness=0.5, prereqs=()),  # prereq of dependent
    ]
    topics[0] = _topic("dependent", readiness=0.5, weight=2.0, prereqs=("foundation",))
    school = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(120), scope=ExamScope.SCHOOL, asof=ASOF)
    comp = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(120), scope=ExamScope.COMPETITIVE, asof=ASOF)
    # Foundation (the prerequisite) ranks at least as high under competitive scope.
    f_school = min(s.priority_rank for s in school.sessions if s.topic_id == "foundation")
    f_comp = min(s.priority_rank for s in comp.sessions if s.topic_id == "foundation")
    assert f_comp <= f_school


# --- re-plan on missed sessions --------------------------------------------
def test_replan_after_missed_rebalances_into_remaining_days():
    topics = [_topic("a", readiness=0.3, base=40), _topic("b", readiness=0.3, base=40)]
    plan = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(60), asof=ASOF)
    # A week passes and the first two days were missed; re-plan from a later date.
    later = date(2026, 6, 8)
    replanned = replan_after_missed(
        plan, topics=topics, available=AvailableTime(60),
        missed_days={date(2026, 6, 1), date(2026, 6, 2)}, asof=later,
    )
    assert replanned.days_available < plan.days_available
    assert "replanned" in replanned.plain_language


def test_replan_is_honest_when_time_now_too_tight():
    topics = [_topic(f"t{i}", readiness=0.0, evidence=False, base=60) for i in range(8)]
    plan = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(60), asof=ASOF)
    near_exam = date(2026, 6, 19)  # only ~2 days left
    replanned = replan_after_missed(
        plan, topics=topics, available=AvailableTime(60),
        missed_days={date(2026, 6, 1)}, asof=near_exam,
    )
    assert replanned.fits is False
    assert "tight" in replanned.plain_language or "protect" in replanned.plain_language


# --- time-left achievability -----------------------------------------------
def test_achievable_forecast_projects_gain_from_planned_minutes():
    topics = [_topic("a", readiness=0.3, base=80)]
    plan = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(120), asof=ASOF)
    fc = achievable_forecast(plan, topics=topics)
    assert fc.achievable_overall >= fc.current_overall
    a = fc.topics[0]
    assert a.projected_readiness >= a.current_readiness


def test_achievable_diminishing_returns_when_time_short():
    topics = [_topic("a", readiness=0.0, evidence=False, base=200)]
    short_exam = date(2026, 6, 3)
    plan = build_plan(exam_date=short_exam, topics=topics, available=AvailableTime(20), asof=ASOF)
    fc = achievable_forecast(plan, topics=topics)
    # Cannot reach full readiness from scratch in two short days.
    assert fc.achievable_overall < 0.8


def test_achievable_weightage_drives_overall():
    topics = [_topic("a", weight=9.0, readiness=0.9), _topic("b", weight=1.0, readiness=0.1, evidence=False)]
    plan = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(120), asof=ASOF)
    fc = achievable_forecast(plan, topics=topics)
    # The heavy, strong topic dominates the overall.
    assert fc.current_overall > 0.6


def test_achievable_plain_language_never_a_percentage():
    topics = [_topic("a", readiness=0.5)]
    plan = build_plan(exam_date=EXAM, topics=topics, available=AvailableTime(120), asof=ASOF)
    fc = achievable_forecast(plan, topics=topics)
    assert "%" not in fc.plain_language
