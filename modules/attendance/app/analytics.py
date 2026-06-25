"""Attendance analytics — rollups over CONFIRMED marks (B8 / d8).

Capture produces marks, the teacher confirms a roll, risk detection turns a
record into signals. This module is the rollup layer that the briefing /
school-wide-intelligence surfaces read: it aggregates *confirmed* rolls into
plain attendance summaries and turns per-learner risk findings into a ranked,
deduped intervention list — "which classes are behind, which students need
intervention".

WHAT IT DOES, DELIBERATELY:

  - :func:`session_summary` / :func:`cohort_summary` — count present-like vs
    absent across one or many :class:`~app.capture.FinalisedRoll`, with the
    attendance rate as a derived metric (never a stored truth).
  - :func:`subject_summary` — per-subject attendance rate from a learner-history
    record (the same shape ``risk.detect_risks`` consumes), so a subject the
    learner repeatedly skips is visible alongside the EXAM-SHORTAGE eligibility
    signal that ``risk.py`` already computes.
  - :func:`intervention_list` — orders unique learners by risk severity (urgent
    -> concern -> watch), so the briefing shows who needs a human's attention
    first. Each entry stays a SIGNAL: it carries ``needs_human_review`` and the
    finding's own rationale; analytics ranks, it does not decide.

INVARIANTS:
  - Analytics reads ONLY confirmed state (``FinalisedRoll``) and risk findings —
    never a draft. A summary is computed from finalised, human-owned marks.
  - PII-free: opaque ``canonical_uuid`` only; no name, no count of a person.
  - Pure + offline: plain functions over in-memory data; no I/O, no provider,
    no secret read. It computes; the event layer (``events.py``) and the
    gateway carry anything across a boundary.
  - It is a VIEW, not a verdict. A rate is a derived number with its evidence
    counts attached; an intervention entry recommends, a human acts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, List, Mapping, Optional, Sequence

from .capture import FinalisedRoll, Status, _PRESENT_LIKE
from .risk import RiskFinding, RiskSeverity

# Statuses that count toward the denominator of an attendance rate. EXCUSED is
# present-like (an approved absence is attendance, not a miss); UNKNOWN must be
# resolved before a roll is confirmed, so a finalised roll should not carry it —
# if one slips through we exclude it from the rate rather than guess.
_COUNTED = frozenset({Status.PRESENT, Status.ABSENT, Status.LATE, Status.EXCUSED})


def _rate(present_like: int, counted: int) -> Optional[float]:
    """Attendance rate in [0,1], or ``None`` when there is nothing to divide.

    A rate over zero counted marks is undefined, not zero — we return ``None``
    so a caller never reads "0% attendance" off an empty record.
    """
    if counted <= 0:
        return None
    return round(present_like / counted, 4)


@dataclass(frozen=True)
class AttendanceSummary:
    """A plain rollup of confirmed marks. A VIEW, never a verdict.

    ``rate`` is derived (present-like / counted) and is ``None`` when nothing
    countable is present. ``scope_id`` labels what the summary is over (a
    session id, a class/cohort id, a subject) for the surface to key on.
    """

    scope_id: str
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0
    unknown: int = 0

    @property
    def counted(self) -> int:
        """Marks that count toward the rate (everything but UNKNOWN)."""
        return self.present + self.absent + self.late + self.excused

    @property
    def present_like(self) -> int:
        """Marks that count as in-attendance (present + late + excused)."""
        return self.present + self.late + self.excused

    @property
    def total(self) -> int:
        return self.counted + self.unknown

    @property
    def rate(self) -> Optional[float]:
        return _rate(self.present_like, self.counted)


def _tally(scope_id: str, statuses: Sequence[Status]) -> AttendanceSummary:
    counts = {s: 0 for s in (Status.PRESENT, Status.ABSENT, Status.LATE,
                             Status.EXCUSED, Status.UNKNOWN)}
    for st in statuses:
        counts[st] = counts.get(st, 0) + 1
    return AttendanceSummary(
        scope_id=scope_id,
        present=counts[Status.PRESENT],
        absent=counts[Status.ABSENT],
        late=counts[Status.LATE],
        excused=counts[Status.EXCUSED],
        unknown=counts[Status.UNKNOWN],
    )


def session_summary(roll: FinalisedRoll) -> AttendanceSummary:
    """Roll up one CONFIRMED session into an attendance summary.

    Takes a :class:`~app.capture.FinalisedRoll` (not a draft — analytics reads
    only human-confirmed state). ``scope_id`` is the session id.
    """
    return _tally(roll.session_id, [m.status for m in roll.marks])


def cohort_summary(
    rolls: Sequence[FinalisedRoll], scope_id: str = "cohort"
) -> AttendanceSummary:
    """Roll up many CONFIRMED rolls (a class, a day, a cohort) into one summary.

    Sums the marks across every finalised roll supplied. ``scope_id`` labels the
    cohort for the surface; the rate is derived from the combined counts.
    """
    statuses: List[Status] = [m.status for roll in rolls for m in roll.marks]
    return _tally(scope_id, statuses)


def _parse_day(day: str) -> date:
    return datetime.fromisoformat(day).date() if "T" in day else date.fromisoformat(day)


def subject_summary(history: Mapping[str, Any]) -> List[AttendanceSummary]:
    """Per-SUBJECT attendance rate from one learner's history.

    ``history`` is the shape ``risk.detect_risks`` consumes:
    ``{"canonical_uuid", "days": [{"date", "status", "subject"?}, ...]}``. Days
    without a subject are grouped under ``"(unspecified)"`` so nothing is lost.
    Returned summaries are sorted by lowest attendance rate first — the subject
    most at risk surfaces at the top — so subject-shortage is visible next to
    the EXAM-SHORTAGE eligibility signal ``risk.py`` already computes.
    """
    days = history.get("days", []) or []
    by_subject: dict[str, List[Status]] = {}
    for d in days:
        subject = d.get("subject") or "(unspecified)"
        try:
            st = d.get("status")
            st = st if isinstance(st, Status) else Status(str(st))
        except ValueError:
            st = Status.UNKNOWN
        by_subject.setdefault(subject, []).append(st)

    summaries = [_tally(subject, statuses) for subject, statuses in by_subject.items()]
    # Lowest rate first; a None rate (no countable marks) sorts last.
    summaries.sort(key=lambda s: (s.rate is None, s.rate if s.rate is not None else 1.0))
    return summaries


# Severity ordering for ranking — urgent first. A finding with an unrecognised
# severity sorts last (after every known band) rather than crashing the sort.
_SEVERITY_RANK = {
    RiskSeverity.URGENT.value: 0,
    RiskSeverity.CONCERN.value: 1,
    RiskSeverity.WATCH.value: 2,
}


@dataclass(frozen=True)
class InterventionEntry:
    """One learner the briefing should surface for attention. A SIGNAL.

    Ranked by the highest-severity finding for that learner; carries every
    contributing risk kind and the top finding's plain-language rationale.
    ``needs_human_review`` stays ``True`` — analytics orders the queue, a human
    decides and owns any response (parent communication, catch-up plan).
    """

    canonical_uuid: str
    severity: str
    risk_kinds: Sequence[str] = field(default_factory=tuple)
    rationale: str = ""
    finding_count: int = 0
    needs_human_review: bool = True


def intervention_list(findings: Sequence[RiskFinding]) -> List[InterventionEntry]:
    """Rank unique learners by risk for the briefing's "needs intervention".

    Collapses every finding for a learner into one entry at that learner's
    highest severity, listing the contributing risk kinds, and orders the list
    urgent -> concern -> watch (then by how many findings stacked up). Each entry
    is a recommendation, never a verdict (``needs_human_review`` is always True).
    """
    by_learner: dict[str, List[RiskFinding]] = {}
    for f in findings:
        by_learner.setdefault(f.canonical_uuid, []).append(f)

    entries: List[InterventionEntry] = []
    for cuid, learner_findings in by_learner.items():
        top = min(
            learner_findings,
            key=lambda f: (_SEVERITY_RANK.get(f.severity, 99), -f.confidence),
        )
        # Preserve first-seen order of risk kinds, deduped.
        kinds: List[str] = []
        for f in learner_findings:
            if f.risk_kind not in kinds:
                kinds.append(f.risk_kind)
        entries.append(
            InterventionEntry(
                canonical_uuid=cuid,
                severity=top.severity,
                risk_kinds=tuple(kinds),
                rationale=top.rationale,
                finding_count=len(learner_findings),
            )
        )

    entries.sort(
        key=lambda e: (_SEVERITY_RANK.get(e.severity, 99), -e.finding_count)
    )
    return entries
