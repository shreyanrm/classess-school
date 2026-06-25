"""Academic year, working days, and holidays as governed config (B1).

The spec (Setup behaviour + /admin/calendar) calls for "academic year, working
days/holidays" as part of the institution's configuration, with policy overlays.
This module makes that real and board-agnostic:

  - :class:`AcademicYear` — a named span (``start`` .. ``end`` inclusive) plus a
    weekly working-day pattern (which weekdays are instructional) and a list of
    :class:`Holiday` closures (single-day or ranged). All values are the
    institution's own DATA — no real calendar, no region hard-coded.
  - Working-day arithmetic: ``is_working_day``, ``working_days``,
    ``working_days_between``, ``instructional_day_count`` — the basis pacing and
    timetable (b2) build on, and the basis "instructional time lost" is measured
    against.

The calendar is HYPERLOCALIZATION as policy: it is stored at a node and
INHERITS down the hierarchy via a well-known policy key (see
:data:`CALENDAR_POLICY_KEY`), so a region can default a year and a campus refine
it, versioned with effective dates like any other policy. This module owns only
the calendar's SHAPE + arithmetic; :mod:`app.policy` owns inheritance.

No PII — a holiday/working-day is institution data, never a person. Pure,
import-safe: stdlib only (``datetime``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Optional


# The well-known policy key under which an academic-year config travels down the
# hierarchy (resolved by app.policy, effective-dated + inheritable like any
# policy). The VALUE is a serialised AcademicYear (see ``to_policy_value``).
CALENDAR_POLICY_KEY = "calendar.academic_year"


class CalendarError(ValueError):
    """A calendar rule was violated (bad span, holiday outside the year)."""


def _iter_days(start: date, end_inclusive: date) -> Iterable[date]:
    day = start
    while day <= end_inclusive:
        yield day
        day += timedelta(days=1)


@dataclass(frozen=True)
class Holiday:
    """A closure within an academic year. ``start``..``end`` inclusive; a single
    day when ``end is None`` (normalised to ``start``). ``label`` is the
    institution's own name for it (data, never PII)."""

    label: str
    start: date
    end: Optional[date] = None

    def __post_init__(self) -> None:
        if self.end is not None and self.end < self.start:
            raise CalendarError("Holiday end must be on/after its start.")

    @property
    def last_day(self) -> date:
        return self.end if self.end is not None else self.start

    def covers(self, day: date) -> bool:
        return self.start <= day <= self.last_day

    def days(self) -> list[date]:
        return list(_iter_days(self.start, self.last_day))


# Monday=0 .. Sunday=6 (datetime.date.weekday convention). The DEFAULT working
# week is Mon–Fri, but it is CONFIGURABLE per institution (a six-day school sets
# its own pattern) — never hard-coded to one region's week.
DEFAULT_WORKING_WEEKDAYS: frozenset[int] = frozenset({0, 1, 2, 3, 4})


@dataclass(frozen=True)
class AcademicYear:
    """A named academic year: span + weekly working pattern + holidays.

    ``working_weekdays`` is the set of instructional weekdays (Mon=0..Sun=6),
    configurable per institution. A working day is any day inside the span that
    is an instructional weekday and not covered by a holiday.
    """

    label: str
    start: date
    end: date
    working_weekdays: frozenset[int] = DEFAULT_WORKING_WEEKDAYS
    holidays: tuple[Holiday, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise CalendarError("Academic year end must be on/after its start.")
        if not self.working_weekdays:
            raise CalendarError("An academic year needs at least one working weekday.")
        for wd in self.working_weekdays:
            if not 0 <= wd <= 6:
                raise CalendarError(f"Working weekday {wd!r} out of range (0..6).")
        for hol in self.holidays:
            if hol.last_day < self.start or hol.start > self.end:
                raise CalendarError(
                    f"Holiday {hol.label!r} falls outside the academic year span."
                )

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def is_holiday(self, day: date) -> bool:
        return any(h.covers(day) for h in self.holidays)

    def is_working_day(self, day: date) -> bool:
        """True iff ``day`` is inside the year, an instructional weekday, and not
        a holiday."""
        return (
            self.contains(day)
            and day.weekday() in self.working_weekdays
            and not self.is_holiday(day)
        )

    def working_days(
        self, *, frm: Optional[date] = None, to: Optional[date] = None
    ) -> list[date]:
        """All working days in the year, optionally clamped to ``frm``..``to``
        (inclusive). The basis for instructional-day counting."""
        lo = max(self.start, frm) if frm is not None else self.start
        hi = min(self.end, to) if to is not None else self.end
        return [d for d in _iter_days(lo, hi) if self.is_working_day(d)]

    def working_days_between(self, frm: date, to: date) -> int:
        """Count of working days in ``frm``..``to`` inclusive (clamped to the
        year). Negative spans count zero. The unit pacing-protection (b2) uses to
        measure planned vs delivered instructional time."""
        if to < frm:
            return 0
        return len(self.working_days(frm=frm, to=to))

    def instructional_day_count(self) -> int:
        """Total instructional (working) days in the whole year."""
        return len(self.working_days())

    # -- policy interop (hyperlocalization via app.policy) ------------------
    def to_policy_value(self) -> dict:
        """Serialise to a JSON-friendly policy value (what app.policy stores +
        inherits + versions under :data:`CALENDAR_POLICY_KEY`)."""
        return {
            "label": self.label,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "working_weekdays": sorted(self.working_weekdays),
            "holidays": [
                {
                    "label": h.label,
                    "start": h.start.isoformat(),
                    "end": h.last_day.isoformat(),
                }
                for h in self.holidays
            ],
        }

    @classmethod
    def from_policy_value(cls, value: dict) -> "AcademicYear":
        """Rebuild from the serialised policy value (the inverse of
        :meth:`to_policy_value`). Validates the span/holidays on construction."""
        holidays = tuple(
            Holiday(
                label=h["label"],
                start=date.fromisoformat(h["start"]),
                end=date.fromisoformat(h["end"]),
            )
            for h in value.get("holidays", [])
        )
        wd = value.get("working_weekdays")
        working = (
            frozenset(int(x) for x in wd) if wd is not None else DEFAULT_WORKING_WEEKDAYS
        )
        return cls(
            label=value["label"],
            start=date.fromisoformat(value["start"]),
            end=date.fromisoformat(value["end"]),
            working_weekdays=working,
            holidays=holidays,
        )
