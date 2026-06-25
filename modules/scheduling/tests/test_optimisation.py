"""Academic-calendar continuous optimisation: instructional time lost,
re-projection of completion, calendar-level recommendation, never auto-commits."""

from __future__ import annotations

from datetime import date

import pytest

from app.calendar import AcademicCalendar, CalendarException, Term
from app.optimisation import (
    CalendarActionKind,
    apply_calendar_recovery,
    instructional_time_delta,
    optimise_after_change,
    project_completion,
    recommend_calendar_response,
    with_exception,
)
from app.pacing import PacingPlan


INST = "11110000-0000-4000-8000-000000000001"
APPROVER = "dddd0000-0000-4000-8000-000000000009"

WINDOW_START = date(2026, 6, 1)
WINDOW_END = date(2026, 6, 26)  # 4 full Mon-Fri weeks = 20 working days.


def _cal() -> AcademicCalendar:
    cal = AcademicCalendar(institution_id=INST, label="Academic Year 2026-27")
    cal.add_term(Term("t1", "Term 1", WINDOW_START, WINDOW_END))
    return cal


def _plan(planned: int = 20, ppwd: float = 1.0) -> PacingPlan:
    return PacingPlan(
        section_id="S10B",
        subject_id="math",
        planned_periods=planned,
        working_days_total=20,
        periods_per_working_day=ppwd,
    )


# -- instructional time lost / gained --------------------------------------


def test_declared_holiday_loses_one_instructional_day():
    before = _cal()
    closure = CalendarException(date(2026, 6, 10), "holiday", "Closure")  # a Wed.
    after = with_exception(before, closure)
    delta = instructional_time_delta(
        before, after, window_start=WINDOW_START, window_end=WINDOW_END
    )
    assert delta.before_working_days == 20
    assert delta.after_working_days == 19
    assert delta.lost == 1
    assert delta.gained == 0
    assert "1 instructional day" in delta.describe()


def test_with_exception_does_not_mutate_the_original_calendar():
    before = _cal()
    n_before = len(before.exceptions)
    with_exception(before, CalendarException(date(2026, 6, 10), "holiday", "x"))
    assert len(before.exceptions) == n_before  # original untouched.


def test_compensatory_override_recovers_an_instructional_day():
    before = _cal()
    after = with_exception(
        before, CalendarException(date(2026, 6, 6), "working_override", "Comp day")
    )  # a Saturday made working.
    delta = instructional_time_delta(
        before, after, window_start=WINDOW_START, window_end=WINDOW_END
    )
    assert delta.gained == 1
    assert delta.lost == 0


# -- re-projecting completion ----------------------------------------------


def test_projection_fits_when_capacity_exceeds_remaining():
    cal = _cal()
    # 20 planned at 1/day; from 2026-06-15 there are 10 working days left. With
    # 12 already delivered only 8 remain -> fits inside the 10-day capacity.
    proj = project_completion(cal, _plan(20, 1.0), as_of=date(2026, 6, 15), delivered_periods=12)
    assert proj.remaining_periods == 8.0
    assert proj.remaining_working_days == 10
    assert proj.verdict in ("fits", "tight")
    assert proj.overrun_periods == 0.0


def test_projection_overruns_when_too_little_time_remains():
    # A tiny remaining window cannot hold the remaining syllabus.
    cal = AcademicCalendar(institution_id=INST, label="Short")
    cal.add_term(Term("t1", "Term 1", date(2026, 6, 22), date(2026, 6, 23)))  # Mon-Tue.
    proj = project_completion(
        cal, _plan(20, 1.0), as_of=date(2026, 6, 22), delivered_periods=5
    )
    # 2 working days x 1/day = 2 capacity vs 15 remaining -> overrun 13.
    assert proj.remaining_working_days == 2
    assert proj.capacity_periods == 2.0
    assert proj.overrun_periods == 13.0
    assert proj.verdict == "overruns"
    assert proj.confidence_band == "low"


def test_projection_requires_a_term():
    cal = AcademicCalendar(institution_id=INST, label="No terms")
    with pytest.raises(ValueError):
        project_completion(cal, _plan(), as_of=WINDOW_START, delivered_periods=0)


# -- calendar-level recommendation -----------------------------------------


def test_no_action_when_nothing_lost():
    cal = _cal()
    before = _cal()
    delta = instructional_time_delta(before, cal, window_start=WINDOW_START, window_end=WINDOW_END)
    proj = project_completion(cal, _plan(20, 1.0), as_of=date(2026, 6, 15), delivered_periods=5)
    rec = recommend_calendar_response(cal, delta, [proj])
    assert rec.kind is CalendarActionKind.NONE
    assert rec.is_consequential is False
    assert rec.ladder_stage == "inform"


def test_lost_time_with_overrun_recommends_a_compensatory_day():
    before = _cal()
    # Lose a Wednesday mid-term.
    after = with_exception(before, CalendarException(date(2026, 6, 17), "holiday", "Closure"))
    delta = instructional_time_delta(before, after, window_start=WINDOW_START, window_end=WINDOW_END)
    assert delta.lost == 1
    # From Mon 2026-06-15 there are 9 working days left (the 17th is now lost) at
    # 2/day -> 18 capacity; 40 planned, 0 delivered -> overruns. A free Saturday
    # (2026-06-20) lies ahead, so a compensatory day is offerable.
    overrun = project_completion(after, _plan(40, 2.0), as_of=date(2026, 6, 15), delivered_periods=0)
    assert overrun.verdict == "overruns"
    rec = recommend_calendar_response(after, delta, [overrun], owner_ref=APPROVER)
    assert rec.kind is CalendarActionKind.COMPENSATORY_DAY
    assert rec.is_consequential is True
    assert rec.ladder_stage == "execute_with_permission"
    # The candidate is a real free in-term day (a Saturday or Sunday here).
    assert rec.candidate_day is not None
    assert after.is_working_day(rec.candidate_day) is False


def test_repace_when_no_free_day_to_recover():
    # A six-day week (Mon-Sat) with no spare weekday to make working leaves only
    # Sundays — but if those are out of term, there is nothing to compensate with.
    cal = AcademicCalendar(
        institution_id=INST, label="Six-day", working_weekdays=(0, 1, 2, 3, 4, 5)
    )
    cal.add_term(Term("t1", "Term 1", date(2026, 6, 22), date(2026, 6, 26)))  # Mon-Fri only.
    before = AcademicCalendar(
        institution_id=INST, label="Six-day", working_weekdays=(0, 1, 2, 3, 4, 5)
    )
    before.add_term(Term("t1", "Term 1", date(2026, 6, 22), date(2026, 6, 26)))
    after = with_exception(cal, CalendarException(date(2026, 6, 24), "holiday", "Closure"))
    delta = instructional_time_delta(before, after, window_start=date(2026, 6, 22), window_end=date(2026, 6, 26))
    assert delta.lost == 1
    overrun = project_completion(after, _plan(40, 2.0), as_of=date(2026, 6, 22), delivered_periods=0)
    rec = recommend_calendar_response(after, delta, [overrun])
    # No in-term Saturday/Sunday available (term is Mon-Fri) -> re-pace.
    assert rec.kind is CalendarActionKind.REPACE


# -- the continuous-optimisation loop --------------------------------------


def test_optimise_after_change_returns_the_full_picture():
    before = _cal()
    after = with_exception(before, CalendarException(date(2026, 6, 17), "holiday", "Closure"))
    plans = [_plan(40, 2.0)]  # demands the whole window; a lost day bites.
    report = optimise_after_change(
        before,
        after,
        plans,
        as_of=date(2026, 6, 22),
        delivered_by_plan={"S10B:math": 0},
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        working_days_elapsed_by_plan={"S10B:math": 15},
        owner_ref=APPROVER,
    )
    assert report.delta.lost == 1
    assert len(report.projections) == 1
    assert len(report.pacing) == 1
    assert report.needs_action is True
    assert report.recommendation.kind in (
        CalendarActionKind.COMPENSATORY_DAY,
        CalendarActionKind.REPACE,
    )


# -- applying a recovery is human-gated ------------------------------------


def test_apply_calendar_recovery_requires_approval():
    before = _cal()
    after = with_exception(before, CalendarException(date(2026, 6, 17), "holiday", "Closure"))
    delta = instructional_time_delta(before, after, window_start=WINDOW_START, window_end=WINDOW_END)
    overrun = project_completion(after, _plan(40, 2.0), as_of=date(2026, 6, 15), delivered_periods=0)
    rec = recommend_calendar_response(after, delta, [overrun])
    assert rec.kind is CalendarActionKind.COMPENSATORY_DAY

    with pytest.raises(PermissionError):
        apply_calendar_recovery(after, rec, approved_by=None)

    # Approved: a working_override is appended and the day becomes working.
    exc = apply_calendar_recovery(after, rec, approved_by=APPROVER)
    assert exc.kind == "working_override"
    assert after.is_working_day(exc.day) is True


def test_apply_refuses_a_repace_recommendation():
    cal = _cal()
    before = _cal()
    delta = instructional_time_delta(before, cal, window_start=WINDOW_START, window_end=WINDOW_END)
    # A NONE recommendation (informational) — not applicable to the calendar.
    rec = recommend_calendar_response(cal, delta, [])
    assert rec.kind is CalendarActionKind.NONE
    with pytest.raises(ValueError):
        apply_calendar_recovery(cal, rec, approved_by=APPROVER)
