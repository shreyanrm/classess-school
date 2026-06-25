"""Academic year, working days, holidays — working-day arithmetic + policy interop."""

from __future__ import annotations

from datetime import date

import pytest

from app.calendar import (
    AcademicYear,
    Holiday,
    CalendarError,
    CALENDAR_POLICY_KEY,
    DEFAULT_WORKING_WEEKDAYS,
)
from app.hierarchy import build_hierarchy
from app.policy import PolicySet


def _year() -> AcademicYear:
    # A short fictional year for arithmetic: Mon 1 Jun 2026 .. Fri 12 Jun 2026.
    return AcademicYear(
        label="AY 2026 (sample)",
        start=date(2026, 6, 1),   # Monday
        end=date(2026, 6, 12),    # Friday
        holidays=(Holiday(label="Founders Day", start=date(2026, 6, 3)),),
    )


def test_default_working_week_is_mon_to_fri():
    assert DEFAULT_WORKING_WEEKDAYS == frozenset({0, 1, 2, 3, 4})


def test_is_working_day_excludes_weekends_and_holidays():
    ay = _year()
    assert ay.is_working_day(date(2026, 6, 1)) is True    # Monday
    assert ay.is_working_day(date(2026, 6, 3)) is False    # holiday (Founders Day)
    assert ay.is_working_day(date(2026, 6, 6)) is False    # Saturday
    assert ay.is_working_day(date(2026, 5, 31)) is False   # outside the year


def test_working_day_counts():
    ay = _year()
    # 1..12 Jun: weekdays Mon1 Tue2 Wed3 Thu4 Fri5 Mon8 Tue9 Wed10 Thu11 Fri12 = 10
    # minus the Wed3 holiday = 9 instructional days.
    assert ay.instructional_day_count() == 9
    # A clamped span: Mon 1 .. Fri 5, minus the Wed3 holiday = 4.
    assert ay.working_days_between(date(2026, 6, 1), date(2026, 6, 5)) == 4
    # Reversed span counts zero.
    assert ay.working_days_between(date(2026, 6, 5), date(2026, 6, 1)) == 0


def test_configurable_six_day_week():
    ay = AcademicYear(
        label="six-day",
        start=date(2026, 6, 1),
        end=date(2026, 6, 7),
        working_weekdays=frozenset({0, 1, 2, 3, 4, 5}),  # Mon..Sat
    )
    # Mon1..Sun7 with Sat working, Sun off = 6 working days.
    assert ay.instructional_day_count() == 6
    assert ay.is_working_day(date(2026, 6, 6)) is True   # Saturday now works
    assert ay.is_working_day(date(2026, 6, 7)) is False  # Sunday still off


def test_ranged_holiday():
    ay = AcademicYear(
        label="with-break",
        start=date(2026, 6, 1),
        end=date(2026, 6, 12),
        holidays=(Holiday(label="Mid-term break", start=date(2026, 6, 8),
                          end=date(2026, 6, 10)),),
    )
    for d in (date(2026, 6, 8), date(2026, 6, 9), date(2026, 6, 10)):
        assert ay.is_working_day(d) is False
    assert ay.is_working_day(date(2026, 6, 11)) is True


def test_bad_spans_rejected():
    with pytest.raises(CalendarError):
        AcademicYear(label="x", start=date(2026, 6, 12), end=date(2026, 6, 1))
    with pytest.raises(CalendarError):
        Holiday(label="x", start=date(2026, 6, 5), end=date(2026, 6, 1))
    with pytest.raises(CalendarError):
        # Holiday outside the year.
        AcademicYear(label="x", start=date(2026, 6, 1), end=date(2026, 6, 5),
                     holidays=(Holiday(label="off", start=date(2026, 7, 1)),))
    with pytest.raises(CalendarError):
        AcademicYear(label="x", start=date(2026, 6, 1), end=date(2026, 6, 5),
                     working_weekdays=frozenset())


def test_policy_roundtrip_serialisation():
    ay = _year()
    value = ay.to_policy_value()
    rebuilt = AcademicYear.from_policy_value(value)
    assert rebuilt.label == ay.label
    assert rebuilt.start == ay.start and rebuilt.end == ay.end
    assert rebuilt.instructional_day_count() == ay.instructional_day_count()
    assert rebuilt.working_weekdays == ay.working_weekdays


def test_calendar_inherits_down_the_hierarchy_as_policy():
    spec = [
        {"key": "r", "kind": "region", "label": "Region West", "parent": None},
        {"key": "s", "kind": "school", "label": "Senior School", "parent": "r"},
        {"key": "sec", "kind": "section", "label": "Section 10-B", "parent": "s"},
    ]
    h = build_hierarchy("tenant-A", spec)
    ids = {n.label: n.id for n in h.all_nodes()}
    ps = PolicySet(h)
    # Region defaults a calendar; it inherits down to the section, versioned.
    ay = _year()
    ps.set_policy(ids["Region West"], CALENDAR_POLICY_KEY, ay.to_policy_value())
    resolved = ps.resolve(ids["Section 10-B"], CALENDAR_POLICY_KEY)
    assert resolved is not None and resolved.inherited is True
    rebuilt = AcademicYear.from_policy_value(resolved.value)
    assert rebuilt.instructional_day_count() == 9
