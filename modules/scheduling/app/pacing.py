"""Pacing protection + teacher knowledge transfer (B2).

Pacing protection tracks planned-vs-delivered periods per section+subject and
flags DRIFT before a syllabus quietly falls behind. The honest denominator is
working days from the academic calendar (so holidays never read as "behind") ×
periods-per-working-day; the numerator is periods actually delivered.

Drift is the gap between what should have been delivered by a date and what was.
It is classified into plain-language bands so a coordinator sees "on track" /
"slipping" / "behind" / "at risk", each with evidence, an owner, and the
consequence of ignoring — mirroring the A5 Recommendation contract. Pacing
NEVER reschedules on its own; it surfaces a finding for a human to act on.

Teacher knowledge transfer: when a class changes hands (planned leave, a
substitution, a transfer), the outgoing teacher's continuity note travels with
it — where the class is, what is next, what to watch for — so the incoming
teacher does not restart from zero. The handover note carries opaque refs only;
no PII and no behavioural data beyond the section's curriculum position.

Pure, deterministic, dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


# ---------------------------------------------------------------------------
# Planned-vs-delivered pacing
# ---------------------------------------------------------------------------

DriftBand = Literal["on_track", "slipping", "behind", "at_risk", "ahead"]


@dataclass(frozen=True)
class PacingPlan:
    """The plan for one section+subject: total periods over a working window.

    ``working_days_total`` is the count of working days in the window (from the
    calendar's working-day math), and ``periods_per_working_day`` is how many
    periods of this subject the section gets on a working day on average.
    """

    section_id: str
    subject_id: str
    planned_periods: int  # total periods in the plan (the syllabus length).
    working_days_total: int  # working days across the whole plan window.
    periods_per_working_day: float  # this subject's periods per working day.

    def __post_init__(self) -> None:
        if self.planned_periods < 0:
            raise ValueError("planned_periods must be non-negative.")
        if self.working_days_total < 0:
            raise ValueError("working_days_total must be non-negative.")
        if self.periods_per_working_day < 0:
            raise ValueError("periods_per_working_day must be non-negative.")

    def expected_by(self, working_days_elapsed: int) -> float:
        """Periods that SHOULD have been delivered after this many working days,
        capped at the plan total. Holidays are already excluded because the input
        is working days, not calendar days.
        """
        elapsed = max(0, min(working_days_elapsed, self.working_days_total))
        expected = elapsed * self.periods_per_working_day
        return min(expected, float(self.planned_periods))


@dataclass
class PacingStatus:
    """The computed pacing finding for a section+subject at a point in time."""

    section_id: str
    subject_id: str
    as_of: date
    working_days_elapsed: int
    expected_periods: float
    delivered_periods: int
    owner_role: str = "coordinator"
    owner_ref: str = ""

    @property
    def drift_periods(self) -> float:
        """Signed drift: positive = behind (owe periods), negative = ahead."""
        return round(self.expected_periods - self.delivered_periods, 2)

    @property
    def drift_fraction(self) -> float:
        """Drift as a fraction of expected; 0 when nothing is expected yet."""
        if self.expected_periods <= 0:
            return 0.0
        return round(self.drift_periods / self.expected_periods, 4)

    @property
    def band(self) -> DriftBand:
        frac = self.drift_fraction
        if frac < -0.05:
            return "ahead"
        if frac <= 0.05:
            return "on_track"
        if frac <= 0.15:
            return "slipping"
        if frac <= 0.30:
            return "behind"
        return "at_risk"

    @property
    def is_drifting(self) -> bool:
        return self.band in ("slipping", "behind", "at_risk")

    @property
    def evidence(self) -> str:
        return (
            f"After {self.working_days_elapsed} working day(s), "
            f"{self.delivered_periods} period(s) delivered against "
            f"{self.expected_periods:.1f} expected (drift {self.drift_periods:+.1f})."
        )

    @property
    def consequence_of_ignoring(self) -> str:
        if not self.is_drifting:
            return "No action needed; the section is keeping pace with the plan."
        return (
            "Left unaddressed, the syllabus finishes late and revision time is "
            "compressed before assessments. Recover with extra/combined periods "
            "or a re-paced plan — a human decides; pacing never reschedules itself."
        )

    @property
    def why_am_i_seeing_this(self) -> str:
        return (
            "Delivered periods have drifted from the planned pace for this "
            f"section and subject (band: {self.band}); surfaced to the owner to "
            "decide on recovery."
        )


def assess_pacing(
    plan: PacingPlan,
    *,
    as_of: date,
    working_days_elapsed: int,
    delivered_periods: int,
    owner_ref: str = "",
    owner_role: str = "coordinator",
) -> PacingStatus:
    """Compute the pacing status for a section+subject. Pure; no side effects."""
    if delivered_periods < 0:
        raise ValueError("delivered_periods must be non-negative.")
    return PacingStatus(
        section_id=plan.section_id,
        subject_id=plan.subject_id,
        as_of=as_of,
        working_days_elapsed=max(0, working_days_elapsed),
        expected_periods=round(plan.expected_by(working_days_elapsed), 2),
        delivered_periods=delivered_periods,
        owner_role=owner_role,
        owner_ref=owner_ref,
    )


# ---------------------------------------------------------------------------
# Teacher knowledge transfer (continuity on handover)
# ---------------------------------------------------------------------------

HandoverReason = Literal["planned_leave", "substitution", "transfer", "term_change"]


@dataclass
class HandoverNote:
    """A teacher's knowledge-transfer note that travels with a class on handover.

    Opaque refs + curriculum position only — no PII, no behavioural data beyond
    where the class is and what is next.
    """

    section_id: str
    subject_id: str
    from_teacher_ref: str  # opaque outgoing teacher.
    to_teacher_ref: str | None  # opaque incoming teacher; None when still TBD.
    reason: HandoverReason
    current_topic_id: str  # ontology node the class is on now.
    next_topic_id: str | None = None  # what comes next.
    last_delivered_period: int | None = None  # plan index last covered.
    watch_points: list[str] = field(default_factory=list)  # generic, PII-free.
    prepared_materials: list[str] = field(default_factory=list)  # opaque content ids.

    def __post_init__(self) -> None:
        # Defend the no-PII invariant at the boundary: watch points are generic
        # pedagogical notes, never named students.
        for wp in self.watch_points:
            if not isinstance(wp, str):
                raise TypeError("watch_points must be plain strings (generic, PII-free).")

    @property
    def is_complete(self) -> bool:
        """A note is complete enough to hand over when it states where the class
        is and what is next."""
        return bool(self.current_topic_id) and self.next_topic_id is not None

    def summary(self) -> str:
        nxt = self.next_topic_id or "to be set"
        return (
            f"Handover ({self.reason}) for the section: currently on topic "
            f"{self.current_topic_id}, next {nxt}; "
            f"{len(self.watch_points)} watch-point(s), "
            f"{len(self.prepared_materials)} prepared item(s)."
        )


def build_handover_note(
    *,
    section_id: str,
    subject_id: str,
    from_teacher_ref: str,
    reason: HandoverReason,
    current_topic_id: str,
    to_teacher_ref: str | None = None,
    next_topic_id: str | None = None,
    last_delivered_period: int | None = None,
    watch_points: list[str] | None = None,
    prepared_materials: list[str] | None = None,
) -> HandoverNote:
    """Construct a knowledge-transfer note. Opaque refs only; PII-free."""
    return HandoverNote(
        section_id=section_id,
        subject_id=subject_id,
        from_teacher_ref=from_teacher_ref,
        to_teacher_ref=to_teacher_ref,
        reason=reason,
        current_topic_id=current_topic_id,
        next_topic_id=next_topic_id,
        last_delivered_period=last_delivered_period,
        watch_points=list(watch_points or []),
        prepared_materials=list(prepared_materials or []),
    )
