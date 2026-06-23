"""The academic calendar (B2): terms, holidays, and working-day math.

Board-agnostic by construction. A calendar is a set of terms, a weekly working
pattern (which weekdays are instructional), and a set of dated exceptions
(holidays and one-off non-working days, or an added working Saturday). Nothing
here hard-codes a board, a region, or a real institution name — those are passed
in as opaque ids and generic labels.

The load-bearing capability is honest working-day math: how many instructional
days actually fall between two dates, which the pacing module reads to convert
"periods planned" into "periods that should have been delivered by now". A day
is a working day only when it sits inside a term, on an instructional weekday,
and is not overridden by a non-working exception (an added working day overrides
the weekly pattern the other way).

Import-safe and dependency-free: pure stdlib ``datetime``. No I/O at import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable, Iterator, Literal

# Monday=0 ... Sunday=6, matching ``date.weekday()``.
Weekday = int

# Default instructional week: Monday-Friday. Institutions reconfigure this; the
# calendar never assumes a fixed week. (Many run a six-day week — pass that in.)
DEFAULT_WORKING_WEEKDAYS: tuple[Weekday, ...] = (0, 1, 2, 3, 4)

ExceptionKind = Literal["holiday", "non_working", "working_override"]


@dataclass(frozen=True)
class Term:
    """A contiguous academic term. ``start``/``end`` are inclusive."""

    term_id: str
    label: str  # generic label, e.g. "Term 1" — never a real institution name.
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("term end cannot precede term start.")

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass(frozen=True)
class CalendarException:
    """A dated override of the weekly working pattern.

    - ``holiday`` / ``non_working``: a weekday that would be instructional is
      not (a declared holiday, a closure).
    - ``working_override``: a weekday that would NOT be instructional is made so
      (a compensatory working Saturday).
    """

    day: date
    kind: ExceptionKind
    label: str  # generic label, e.g. "Founders Day" — never PII.

    @property
    def is_working_override(self) -> bool:
        return self.kind == "working_override"


@dataclass
class AcademicCalendar:
    """The academic calendar for one tenant (institution), board-agnostic.

    Keyed by opaque ``institution_id`` only — never a real name. Holds terms, the
    weekly instructional pattern, and dated exceptions. All math derives from
    these three inputs; nothing is hard-coded.
    """

    institution_id: str
    label: str  # generic, e.g. "Academic Year 2026-27".
    terms: list[Term] = field(default_factory=list)
    working_weekdays: tuple[Weekday, ...] = DEFAULT_WORKING_WEEKDAYS
    exceptions: list[CalendarException] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.working_weekdays:
            raise ValueError("a calendar needs at least one instructional weekday.")
        # Normalise + de-duplicate the weekly pattern.
        self.working_weekdays = tuple(sorted({int(w) for w in self.working_weekdays}))
        for w in self.working_weekdays:
            if not 0 <= w <= 6:
                raise ValueError("working_weekdays entries must be 0 (Mon) .. 6 (Sun).")

    # -- exception index ----------------------------------------------------

    def _exception_for(self, day: date) -> CalendarException | None:
        """The governing exception for a day, if any.

        A ``working_override`` wins over a same-day non-working exception so a
        deliberately-added working day is honoured even amid a holiday block.
        """
        match: CalendarException | None = None
        for exc in self.exceptions:
            if exc.day != day:
                continue
            if exc.is_working_override:
                return exc
            match = exc
        return match

    # -- core predicates ----------------------------------------------------

    def term_for(self, day: date) -> Term | None:
        for term in self.terms:
            if term.contains(day):
                return term
        return None

    def in_session(self, day: date) -> bool:
        """True when the day falls inside any term (session is open)."""
        return self.term_for(day) is not None

    def is_working_day(self, day: date) -> bool:
        """A working (instructional) day: in a term, on an instructional weekday
        (or made one by a working_override), and not a holiday/non-working
        exception.
        """
        if not self.in_session(day):
            return False
        exc = self._exception_for(day)
        if exc is not None:
            return exc.is_working_override
        return day.weekday() in self.working_weekdays

    # -- iteration + counting ----------------------------------------------

    def iter_days(self, start: date, end: date) -> Iterator[date]:
        """Yield every calendar date in ``[start, end]`` inclusive."""
        if end < start:
            return
        cur = start
        while cur <= end:
            yield cur
            cur = cur + timedelta(days=1)

    def working_days(self, start: date, end: date) -> list[date]:
        """All working days in ``[start, end]`` inclusive."""
        return [d for d in self.iter_days(start, end) if self.is_working_day(d)]

    def working_day_count(self, start: date, end: date) -> int:
        """Count of working days in ``[start, end]`` inclusive.

        This is the number the pacing module multiplies by periods-per-day to
        get "periods that should have been delivered" — so it must be honest
        about holidays and the weekly pattern, not a naive day difference.
        """
        return sum(1 for _ in self.working_days(start, end))

    def next_working_day(self, day: date, *, inclusive: bool = False) -> date | None:
        """The next working day on or after ``day``.

        Bounded by the last term end so an open-ended search over a closed
        calendar terminates and returns ``None`` rather than looping forever.
        """
        if not self.terms:
            return None
        horizon = max(t.end for t in self.terms)
        cur = day if inclusive else day + timedelta(days=1)
        while cur <= horizon:
            if self.is_working_day(cur):
                return cur
            cur += timedelta(days=1)
        return None

    def add_term(self, term: Term) -> None:
        self.terms.append(term)

    def add_exception(self, exc: CalendarException) -> None:
        self.exceptions.append(exc)

    def add_holidays(self, days: Iterable[tuple[date, str]]) -> None:
        """Convenience: register a batch of holidays as ``(date, label)`` pairs."""
        for day, label in days:
            self.exceptions.append(CalendarException(day=day, kind="holiday", label=label))
