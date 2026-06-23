"""Calendar working-day math: terms, holidays, weekly pattern, overrides."""

from __future__ import annotations

from datetime import date

from app.calendar import AcademicCalendar, CalendarException, Term


INST = "11110000-0000-4000-8000-000000000001"


def _cal() -> AcademicCalendar:
    cal = AcademicCalendar(institution_id=INST, label="Academic Year 2026-27")
    # Term 1: Mon 2026-06-01 .. Fri 2026-06-26 (four full Mon-Fri weeks).
    cal.add_term(Term("t1", "Term 1", date(2026, 6, 1), date(2026, 6, 26)))
    return cal


def test_working_day_excludes_weekends_by_default():
    cal = _cal()
    assert cal.is_working_day(date(2026, 6, 1)) is True  # Monday
    assert cal.is_working_day(date(2026, 6, 6)) is False  # Saturday
    assert cal.is_working_day(date(2026, 6, 7)) is False  # Sunday


def test_out_of_term_is_not_a_working_day():
    cal = _cal()
    # Before the term starts (a Friday) -> not in session.
    assert cal.in_session(date(2026, 5, 29)) is False
    assert cal.is_working_day(date(2026, 5, 29)) is False


def test_holiday_inside_term_is_not_a_working_day():
    cal = _cal()
    cal.add_holidays([(date(2026, 6, 10), "Founders Day")])  # a Wednesday.
    assert cal.is_working_day(date(2026, 6, 10)) is False


def test_working_override_turns_a_saturday_into_a_working_day():
    cal = _cal()
    cal.add_exception(CalendarException(date(2026, 6, 6), "working_override", "Compensatory day"))
    assert cal.is_working_day(date(2026, 6, 6)) is True  # the Saturday now counts.


def test_working_override_wins_over_a_same_day_holiday():
    cal = _cal()
    wed = date(2026, 6, 10)
    cal.add_holidays([(wed, "Tentative holiday")])
    cal.add_exception(CalendarException(wed, "working_override", "Restored working day"))
    assert cal.is_working_day(wed) is True


def test_working_day_count_over_a_full_four_week_term():
    cal = _cal()
    # 2026-06-01 .. 2026-06-26 inclusive: 4 weeks x 5 weekdays = 20 working days.
    count = cal.working_day_count(date(2026, 6, 1), date(2026, 6, 26))
    assert count == 20


def test_working_day_count_subtracts_a_holiday():
    cal = _cal()
    cal.add_holidays([(date(2026, 6, 10), "Founders Day")])
    count = cal.working_day_count(date(2026, 6, 1), date(2026, 6, 26))
    assert count == 19


def test_six_day_week_counts_saturdays():
    cal = AcademicCalendar(
        institution_id=INST,
        label="Six-day week",
        working_weekdays=(0, 1, 2, 3, 4, 5),  # Mon-Sat.
    )
    cal.add_term(Term("t1", "Term 1", date(2026, 6, 1), date(2026, 6, 6)))  # Mon-Sat.
    assert cal.working_day_count(date(2026, 6, 1), date(2026, 6, 6)) == 6


def test_next_working_day_skips_weekend_and_terminates():
    cal = _cal()
    # From Friday 2026-06-05, the next working day is Monday 2026-06-08.
    assert cal.next_working_day(date(2026, 6, 5)) == date(2026, 6, 8)
    # Past the term end it returns None rather than looping forever.
    assert cal.next_working_day(date(2026, 6, 26)) is None


def test_calendar_rejects_inverted_term():
    cal = _cal()
    try:
        Term("bad", "Bad", date(2026, 6, 26), date(2026, 6, 1))
    except ValueError:
        return
    raise AssertionError("expected ValueError for end before start")
