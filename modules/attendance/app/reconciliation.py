"""Reconcile attendance signals across multiple capture methods.

A session may be captured by more than one assisting method (for example a
classroom photo-roster plus an absent-only teacher pass, or an
online-presence feed plus a voice roll-call). This module combines those
draft signals per student and:

- agrees a single suggested status where the methods concur;
- FLAGS a conflict for human review where methods disagree;
- never silently picks a winner on a consequential disagreement - a
  conflict is surfaced, not auto-resolved.

Reconciliation produces a *suggestion*, exactly like capture: it does not
finalise attendance. The teacher still confirms (see
:func:`app.capture.confirm_roll`). Output is PII-free: students are keyed by
``canonical_uuid`` only. Pure, offline, no network or DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .capture import CONFIDENCE_GATE, DraftRoll, Method, Status


@dataclass(frozen=True)
class MethodSignal:
    """One method's opinion about one student."""

    method: Method
    status: Status
    confidence: float


@dataclass(frozen=True)
class ReconciledMark:
    """The reconciled view of a single student across methods.

    ``conflict`` is True when methods disagree on a *material* status and a
    human must decide. ``resolved_status`` is the agreed suggestion when
    there is no conflict, else ``Status.UNKNOWN``.
    """

    canonical_uuid: str
    signals: Sequence[MethodSignal]
    resolved_status: Status
    conflict: bool
    needs_review: bool

    @property
    def methods(self) -> List[str]:
        return [s.method.value for s in self.signals]

    @property
    def statuses(self) -> List[str]:
        return [s.status.value for s in self.signals]


@dataclass(frozen=True)
class ReconciliationResult:
    session_id: str
    marks: Sequence[ReconciledMark]

    @property
    def conflicts(self) -> List[ReconciledMark]:
        """Marks requiring human review because methods disagree."""

        return [m for m in self.marks if m.conflict]

    @property
    def agreed(self) -> List[ReconciledMark]:
        return [m for m in self.marks if not m.conflict]

    def summary(self) -> Dict[str, int]:
        return {
            "students": len(self.marks),
            "conflicts": len(self.conflicts),
            "agreed": len(self.agreed),
            "needs_review": len([m for m in self.marks if m.needs_review]),
        }


# Statuses that, when mixed, are a material conflict needing a human.
# present-vs-absent is the canonical material disagreement. late/excused
# are treated as compatible refinements of present unless paired with
# absent.
_PRESENT_LIKE = {Status.PRESENT, Status.LATE, Status.EXCUSED}


def _is_material_conflict(statuses: Sequence[Status]) -> bool:
    distinct = {s for s in statuses if s is not Status.UNKNOWN}
    if len(distinct) <= 1:
        return False
    has_present_like = any(s in _PRESENT_LIKE for s in distinct)
    has_absent = Status.ABSENT in distinct
    if has_present_like and has_absent:
        return True
    # Disagreement purely among present-like states (present vs late vs
    # excused) is a soft conflict: still surfaced for review but not blocked
    # as material. We treat differing present-like states as needs_review
    # but resolvable to the highest-confidence present-like suggestion.
    return False


def _resolve_present_like(
    signals: Sequence[MethodSignal],
) -> Status:
    present_like = [s for s in signals if s.status in _PRESENT_LIKE]
    if not present_like:
        return Status.UNKNOWN
    best = max(present_like, key=lambda s: s.confidence)
    return best.status


def reconcile_student(
    canonical_uuid: str, signals: Sequence[MethodSignal]
) -> ReconciledMark:
    """Reconcile all method signals for a single student."""

    statuses = [s.status for s in signals]
    conflict = _is_material_conflict(statuses)

    distinct = {s for s in statuses if s is not Status.UNKNOWN}
    soft_disagreement = len(distinct) > 1 and not conflict
    low_conf = any(s.confidence < CONFIDENCE_GATE for s in signals)
    has_unknown = any(s.status is Status.UNKNOWN for s in signals)

    if conflict:
        resolved = Status.UNKNOWN
    elif not distinct:
        resolved = Status.UNKNOWN
    elif len(distinct) == 1:
        resolved = next(iter(distinct))
    else:
        # soft present-like disagreement
        resolved = _resolve_present_like(signals)

    needs_review = conflict or soft_disagreement or low_conf or has_unknown

    return ReconciledMark(
        canonical_uuid=canonical_uuid,
        signals=tuple(signals),
        resolved_status=resolved,
        conflict=conflict,
        needs_review=needs_review,
    )


def _signals_from_drafts(
    drafts: Sequence[DraftRoll],
) -> Dict[str, List[MethodSignal]]:
    by_student: Dict[str, List[MethodSignal]] = {}
    for d in drafts:
        for m in d.marks:
            by_student.setdefault(m.canonical_uuid, []).append(
                MethodSignal(
                    method=m.method,
                    status=m.status,
                    confidence=m.confidence,
                )
            )
    return by_student


def reconcile(drafts: Sequence[DraftRoll]) -> ReconciliationResult:
    """Reconcile several method drafts for the SAME session.

    Raises ``ValueError`` if the drafts are for different sessions (you
    cannot reconcile signals across sessions).
    """

    if not drafts:
        raise ValueError("at least one draft is required to reconcile")

    session_ids = {d.session_id for d in drafts}
    if len(session_ids) != 1:
        raise ValueError("all drafts must belong to the same session_id")
    session_id = next(iter(session_ids))

    by_student = _signals_from_drafts(drafts)
    marks = [
        reconcile_student(cuid, signals)
        for cuid, signals in by_student.items()
    ]
    return ReconciliationResult(session_id=session_id, marks=tuple(marks))


def to_review_payload(result: ReconciliationResult) -> List[Dict[str, object]]:
    """Plain-language conflict list for an explainable review surface.

    Only conflicting marks are returned; each entry names the methods and
    the statuses they reported so a human can decide. PII-free.
    """

    payload: List[Dict[str, object]] = []
    for m in result.conflicts:
        payload.append(
            {
                "canonical_uuid": m.canonical_uuid,
                "methods": m.methods,
                "statuses": m.statuses,
                "needs_human_review": True,
            }
        )
    return payload
