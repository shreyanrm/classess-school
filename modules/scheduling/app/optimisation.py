"""Academic-calendar CONTINUOUS OPTIMISATION (B2).

The document is explicit that the academic calendar is *"not a document prepared
once a term — a continuously optimised operational layer that keeps teaching
going when the day changes"*, and that the engine *"tracks planned vs. delivered
periods and instructional time lost"*.

:mod:`app.calendar` owns the honest working-day math (terms, the weekly pattern,
dated overrides). :mod:`app.pacing` reads it to flag per-section drift. What was
missing is the calendar-level continuous loop that closes between them: when a
holiday or closure is declared MID-TERM, instructional days are LOST, the
working-day denominator shrinks, and every plan that was sized against the
original calendar must be RE-PROJECTED. This module is that loop.

Given a calendar and a plan window it:

  - quantifies INSTRUCTIONAL TIME LOST — how the working-day count changed after
    an exception was added (a declared holiday, a closure), and the converse gain
    when a compensatory working-override is added;
  - RE-PROJECTS each plan: with the revised remaining working days, can the
    syllabus still finish inside the window? It computes the projected
    completion against the term end and the slack/overrun in working days;
  - RECOMMENDS a calendar-level response — recover the lost day with a
    compensatory working-override, or accept a re-pace — surfaced for approval.

Like everything consequential in B2 it NEVER auto-commits. A re-projection is a
read; recommending a calendar change is a recommendation; declaring a
compensatory working day is :func:`apply_calendar_recovery`, a separate,
human-gated step (INVARIANT 8). Every recommendation mirrors the A5
Recommendation contract: evidence, a confidence band, an owner, a consequence,
and a why-am-I-seeing-this line.

Pure, deterministic, dependency-free. Opaque ids + generic labels only; no PII.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Literal

from .calendar import AcademicCalendar, CalendarException
from .pacing import PacingPlan, PacingStatus, assess_pacing


# ---------------------------------------------------------------------------
# Instructional time lost / gained between two views of the calendar
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstructionalTimeDelta:
    """How the working-day count over a window changed between two calendars.

    The honest measure of *"instructional time lost"* the document names: the
    difference in working days that a declared exception caused over the plan
    window. ``lost`` is positive when days were removed (a holiday/closure);
    ``gained`` is positive when a compensatory working-override added days.
    """

    window_start: date
    window_end: date
    before_working_days: int
    after_working_days: int

    @property
    def net_change(self) -> int:
        """Signed change in working days (after - before): negative = days lost."""
        return self.after_working_days - self.before_working_days

    @property
    def lost(self) -> int:
        """Working days removed (>= 0)."""
        return max(0, -self.net_change)

    @property
    def gained(self) -> int:
        """Working days added back by a working-override (>= 0)."""
        return max(0, self.net_change)

    def describe(self) -> str:
        if self.lost:
            return f"{self.lost} instructional day(s) lost over the window."
        if self.gained:
            return f"{self.gained} instructional day(s) recovered over the window."
        return "No change to instructional days over the window."


def instructional_time_delta(
    before: AcademicCalendar,
    after: AcademicCalendar,
    *,
    window_start: date,
    window_end: date,
) -> InstructionalTimeDelta:
    """Quantify instructional time lost/gained between two calendar views.

    Pure read of both calendars' working-day math over the same window — the
    canonical way to measure what a declared holiday/closure (or a compensatory
    working day) did to the instructional denominator. Neither calendar is
    mutated.
    """
    return InstructionalTimeDelta(
        window_start=window_start,
        window_end=window_end,
        before_working_days=before.working_day_count(window_start, window_end),
        after_working_days=after.working_day_count(window_start, window_end),
    )


def with_exception(
    calendar: AcademicCalendar, exception: CalendarException
) -> AcademicCalendar:
    """A COPY of the calendar with one extra exception applied — never mutating
    the original.

    Lets a caller ask *"what would this closure do to instructional time?"*
    without touching the live calendar. The copy shares the frozen term/exception
    values (they are immutable) but holds its own lists.
    """
    return AcademicCalendar(
        institution_id=calendar.institution_id,
        label=calendar.label,
        terms=list(calendar.terms),
        working_weekdays=calendar.working_weekdays,
        exceptions=[*calendar.exceptions, exception],
    )


# ---------------------------------------------------------------------------
# Re-projecting a plan against the revised calendar
# ---------------------------------------------------------------------------

ProjectionVerdict = Literal["fits", "tight", "overruns"]


@dataclass(frozen=True)
class CompletionProjection:
    """Whether a section+subject plan still finishes inside its working window
    after the calendar changed — the continuous re-projection of completion.

    ``remaining_working_days`` is the honest count from the (revised) calendar
    between ``as_of`` and the window end. ``remaining_periods`` is the syllabus
    still to deliver. ``capacity_periods`` is what the remaining working days can
    hold at the plan's pace. The verdict compares the two.
    """

    section_id: str
    subject_id: str
    as_of: date
    remaining_periods: float
    remaining_working_days: int
    periods_per_working_day: float
    owner_role: str = "coordinator"
    owner_ref: str = ""

    @property
    def capacity_periods(self) -> float:
        """Periods the remaining working days can deliver at the plan's pace."""
        return round(self.remaining_working_days * self.periods_per_working_day, 2)

    @property
    def overrun_periods(self) -> float:
        """Periods that will NOT fit in the remaining window (>0 = overrun)."""
        return round(max(0.0, self.remaining_periods - self.capacity_periods), 2)

    @property
    def slack_periods(self) -> float:
        """Spare capacity in the remaining window (>0 = room to absorb a slip)."""
        return round(max(0.0, self.capacity_periods - self.remaining_periods), 2)

    @property
    def verdict(self) -> ProjectionVerdict:
        if self.overrun_periods > 1e-9:
            return "overruns"
        # "tight" when there is under one working day of slack left.
        if self.slack_periods < max(self.periods_per_working_day, 1e-9):
            return "tight"
        return "fits"

    @property
    def confidence_band(self) -> Literal["low", "medium", "high"]:
        if self.verdict == "overruns":
            return "low"
        if self.verdict == "tight":
            return "medium"
        return "high"

    @property
    def evidence(self) -> str:
        return (
            f"{self.remaining_periods:.1f} period(s) remain against "
            f"{self.capacity_periods:.1f} the {self.remaining_working_days} "
            f"remaining working day(s) can hold at {self.periods_per_working_day:.2f}/day "
            f"(overrun {self.overrun_periods:+.1f}, slack {self.slack_periods:.1f})."
        )

    @property
    def consequence_of_ignoring(self) -> str:
        if self.verdict == "overruns":
            return (
                "Left as-is the syllabus cannot finish inside the term: "
                f"~{self.overrun_periods:.1f} period(s) have nowhere to land. "
                "Recover instructional time or re-pace — a human decides."
            )
        if self.verdict == "tight":
            return (
                "The plan still fits but with almost no slack; one more lost day "
                "tips it into overrun. Worth watching."
            )
        return "The plan comfortably fits the remaining working days."

    @property
    def why_am_i_seeing_this(self) -> str:
        return (
            "The academic calendar changed and the plan was re-projected against "
            f"the revised remaining working days (verdict: {self.verdict}); "
            "surfaced to the owner."
        )


def project_completion(
    calendar: AcademicCalendar,
    plan: PacingPlan,
    *,
    as_of: date,
    delivered_periods: int,
    owner_ref: str = "",
    owner_role: str = "coordinator",
) -> CompletionProjection:
    """Re-project whether a plan still finishes inside its window on the CURRENT
    (possibly revised) calendar.

    Reads the honest remaining-working-day count from the calendar between
    ``as_of`` and the window end (the last term end), then compares the syllabus
    still to deliver against what those days can hold at the plan's pace. Pure;
    neither the calendar nor the plan is mutated.
    """
    if delivered_periods < 0:
        raise ValueError("delivered_periods must be non-negative.")
    if not calendar.terms:
        raise ValueError("a calendar with at least one term is needed to project completion.")
    window_end = max(t.end for t in calendar.terms)
    # Remaining working days from today (inclusive) to the window end.
    remaining_wd = calendar.working_day_count(as_of, window_end)
    remaining_periods = max(0.0, float(plan.planned_periods) - delivered_periods)
    return CompletionProjection(
        section_id=plan.section_id,
        subject_id=plan.subject_id,
        as_of=as_of,
        remaining_periods=round(remaining_periods, 2),
        remaining_working_days=remaining_wd,
        periods_per_working_day=plan.periods_per_working_day,
        owner_role=owner_role,
        owner_ref=owner_ref,
    )


# ---------------------------------------------------------------------------
# The calendar-level recommendation (recover lost time vs. re-pace)
# ---------------------------------------------------------------------------


class CalendarActionKind(str, Enum):
    """The calendar-level responses to lost instructional time."""

    # Declare a compensatory working day (turn a non-instructional weekday into
    # an instructional one) to recover the lost capacity.
    COMPENSATORY_DAY = "compensatory_working_day"
    # Accept the loss and re-pace the affected plans (no calendar change).
    REPACE = "repace_plans"
    # Nothing to do — the loss is absorbed by existing slack.
    NONE = "no_action"


CALENDAR_ACTION_LABELS: dict[CalendarActionKind, str] = {
    CalendarActionKind.COMPENSATORY_DAY: "Declare a compensatory working day",
    CalendarActionKind.REPACE: "Re-pace the affected plans",
    CalendarActionKind.NONE: "No calendar action needed",
}


@dataclass
class CalendarRecommendation:
    """A calendar-level recommendation after instructional time was lost.

    NEVER auto-applied. ``ladder_stage`` is ``execute_with_permission`` and
    ``is_consequential`` is True when it proposes a real change — changing the
    calendar (a compensatory day) moves teaching for everyone, so it waits for a
    human (INVARIANT 8). The ``NONE`` action is informational and not
    consequential. :func:`apply_calendar_recovery` is the separate, gated step.
    """

    kind: CalendarActionKind
    institution_id: str
    delta: InstructionalTimeDelta
    affected_sections: list[str] = field(default_factory=list)
    # For a compensatory-day recommendation: a candidate date to make working.
    candidate_day: date | None = None
    owner_role: str = "coordinator"
    owner_ref: str = ""
    ladder_stage: str = "execute_with_permission"
    is_consequential: bool = True

    def __post_init__(self) -> None:
        # No-action is purely informational; it never sits on the permission
        # ladder as a consequential change.
        if self.kind is CalendarActionKind.NONE:
            self.is_consequential = False
            self.ladder_stage = "inform"

    @property
    def label(self) -> str:
        return CALENDAR_ACTION_LABELS[self.kind]

    @property
    def confidence_band(self) -> Literal["low", "medium", "high"]:
        # Recovering a lost day with a compensatory day is a clean, high-confidence
        # fix; re-pacing is a judgement call (medium); no-action is high.
        if self.kind is CalendarActionKind.COMPENSATORY_DAY:
            return "high"
        if self.kind is CalendarActionKind.REPACE:
            return "medium"
        return "high"

    @property
    def evidence(self) -> list[str]:
        lines = [self.delta.describe()]
        if self.affected_sections:
            lines.append(
                f"{len(self.affected_sections)} section/subject plan(s) projected "
                "to overrun the term on the revised calendar"
            )
        if self.candidate_day is not None:
            lines.append(
                f"candidate compensatory day: {self.candidate_day.isoformat()}"
            )
        return lines

    @property
    def why(self) -> str:
        if self.kind is CalendarActionKind.NONE:
            return (
                "Instructional time changed but every affected plan still fits the "
                "term; surfaced for awareness, no action needed."
            )
        return (
            f"{self.label}: {self.delta.describe()} "
            f"{len(self.affected_sections)} plan(s) now project to overrun the term. "
            "Surfaced for your approval; the calendar never reshapes itself."
        )

    @property
    def consequence_of_applying(self) -> str:
        if self.kind is CalendarActionKind.COMPENSATORY_DAY:
            return (
                "Applying this turns a non-instructional day into a working day "
                "for the whole institution, recovering the lost capacity; a human "
                "approves before the calendar changes."
            )
        if self.kind is CalendarActionKind.REPACE:
            return (
                "No calendar change; instead the affected plans are re-paced (extra "
                "or combined periods). Handled by the pacing-recovery flow on approval."
            )
        return "No change is applied."


def recommend_calendar_response(
    calendar: AcademicCalendar,
    delta: InstructionalTimeDelta,
    projections: list[CompletionProjection],
    *,
    owner_ref: str = "",
    owner_role: str = "coordinator",
) -> CalendarRecommendation:
    """Recommend the calendar-level response to lost instructional time.

    Logic, conservative and explainable:
      - no days lost, or no plan overruns -> NO_ACTION (informational);
      - days lost AND at least one plan overruns -> prefer a COMPENSATORY_DAY when
        the calendar offers a free (non-instructional, in-term, not-yet-overridden)
        weekday to make working; otherwise recommend a RE-PACE.

    Never applies anything. The candidate compensatory day is the earliest such
    day on or after the most-pressed projection's ``as_of`` — surfaced, not set.
    """
    overruns = [p for p in projections if p.verdict == "overruns"]
    affected = [f"{p.section_id}:{p.subject_id}" for p in overruns]

    if delta.lost == 0 or not overruns:
        return CalendarRecommendation(
            kind=CalendarActionKind.NONE,
            institution_id=calendar.institution_id,
            delta=delta,
            affected_sections=affected,
            owner_ref=owner_ref,
            owner_role=owner_role,
        )

    earliest_as_of = min(p.as_of for p in overruns)
    candidate = _first_free_weekday(calendar, on_or_after=earliest_as_of)
    kind = (
        CalendarActionKind.COMPENSATORY_DAY
        if candidate is not None
        else CalendarActionKind.REPACE
    )
    return CalendarRecommendation(
        kind=kind,
        institution_id=calendar.institution_id,
        delta=delta,
        affected_sections=affected,
        candidate_day=candidate,
        owner_ref=owner_ref,
        owner_role=owner_role,
    )


def _first_free_weekday(
    calendar: AcademicCalendar, *, on_or_after: date
) -> date | None:
    """The earliest in-term day on/after ``on_or_after`` that is NOT currently a
    working day and has no exception on it — a candidate compensatory day.

    Bounded by the last term end so the search terminates. Pure read.
    """
    if not calendar.terms:
        return None
    horizon = max(t.end for t in calendar.terms)
    existing = {exc.day for exc in calendar.exceptions}
    for day in calendar.iter_days(on_or_after, horizon):
        if not calendar.in_session(day):
            continue
        if day in existing:
            continue
        if not calendar.is_working_day(day):
            return day
    return None


# ---------------------------------------------------------------------------
# The continuous-optimisation loop (read-only): one call, the full picture
# ---------------------------------------------------------------------------


@dataclass
class OptimisationReport:
    """The continuous-optimisation read for one calendar change.

    Bundles the instructional-time delta, the per-plan re-projections, the
    per-plan pacing drift, and the single calendar-level recommendation — the
    whole picture a coordinator needs after the calendar moved. Purely the
    result of reads; nothing is committed.
    """

    institution_id: str
    delta: InstructionalTimeDelta
    projections: list[CompletionProjection]
    pacing: list[PacingStatus]
    recommendation: CalendarRecommendation

    @property
    def overruns(self) -> list[CompletionProjection]:
        return [p for p in self.projections if p.verdict == "overruns"]

    @property
    def needs_action(self) -> bool:
        return self.recommendation.kind is not CalendarActionKind.NONE


def optimise_after_change(
    before: AcademicCalendar,
    after: AcademicCalendar,
    plans: list[PacingPlan],
    *,
    as_of: date,
    delivered_by_plan: dict[str, int],
    window_start: date,
    window_end: date,
    working_days_elapsed_by_plan: dict[str, int] | None = None,
    owner_ref: str = "",
    owner_role: str = "coordinator",
) -> OptimisationReport:
    """Run the continuous-optimisation loop after a calendar change — one read
    that returns the full picture.

    Measures instructional time lost/gained over ``[window_start, window_end]``,
    re-projects every plan against the revised calendar from ``as_of``, computes
    each plan's pacing drift, and produces the single calendar-level
    recommendation. ``delivered_by_plan`` maps ``"section_id:subject_id"`` ->
    periods delivered. NEVER commits — every output is a read or a recommendation
    for a human.
    """
    delta = instructional_time_delta(
        before, after, window_start=window_start, window_end=window_end
    )
    elapsed = working_days_elapsed_by_plan or {}
    projections: list[CompletionProjection] = []
    pacing: list[PacingStatus] = []
    for plan in plans:
        key = f"{plan.section_id}:{plan.subject_id}"
        delivered = delivered_by_plan.get(key, 0)
        projections.append(
            project_completion(
                after,
                plan,
                as_of=as_of,
                delivered_periods=delivered,
                owner_ref=owner_ref,
                owner_role=owner_role,
            )
        )
        pacing.append(
            assess_pacing(
                plan,
                as_of=as_of,
                working_days_elapsed=elapsed.get(key, 0),
                delivered_periods=delivered,
                owner_ref=owner_ref,
                owner_role=owner_role,
            )
        )
    recommendation = recommend_calendar_response(
        after, delta, projections, owner_ref=owner_ref, owner_role=owner_role
    )
    return OptimisationReport(
        institution_id=after.institution_id,
        delta=delta,
        projections=projections,
        pacing=pacing,
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# Applying a calendar recovery — the separate, human-gated step
# ---------------------------------------------------------------------------


def apply_calendar_recovery(
    calendar: AcademicCalendar,
    recommendation: CalendarRecommendation,
    *,
    approved_by: str | None,
    label: str = "Compensatory working day",
) -> CalendarException:
    """Apply an approved COMPENSATORY-DAY recommendation to the live calendar —
    the SEPARATE, explicit, human-gated step.

    Refuses without an ``approved_by`` (an opaque human ref): changing the
    calendar moves teaching for everyone and never auto-fires (INVARIANT 8).
    Only valid for a ``COMPENSATORY_DAY`` recommendation carrying a candidate
    day; a re-pace recommendation is applied by the pacing-recovery flow, not
    here. Appends a ``working_override`` exception (the calendar's own additive,
    audit-friendly mechanism) and returns it. The optimiser never calls this.
    """
    if not approved_by:
        raise PermissionError(
            "Changing the academic calendar is consequential and requires explicit "
            "human approval (approved_by). The optimiser never reshapes the calendar."
        )
    if recommendation.kind is not CalendarActionKind.COMPENSATORY_DAY:
        raise ValueError(
            "only a compensatory-working-day recommendation is applied to the "
            "calendar here; a re-pace is handled by the pacing-recovery flow."
        )
    if recommendation.candidate_day is None:
        raise ValueError("the recommendation carries no candidate compensatory day.")
    exc = CalendarException(
        day=recommendation.candidate_day,
        kind="working_override",
        label=label,
    )
    calendar.add_exception(exc)
    return exc
