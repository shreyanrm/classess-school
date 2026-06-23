"""Staff attendance.

Records daily staff attendance and, when a staff member is absent on a day
with assigned sessions, produces the :class:`SubstitutionNeededEvent` that
asks the scheduling module to begin its substitution ladder.

Like student capture, a staff record is a *draft* until a human confirms
it: marking a colleague absent and triggering substitution cover is a
consequential action, so it never auto-fires. The substitution request is
only built from a CONFIRMED absence.

PII-free: staff are keyed by ``canonical_uuid`` only. Pure, offline.
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Sequence

from .events import SubstitutionNeededEvent, substitution_needed_event
from .safety import assert_no_pii_identifier, screen_free_text


class StaffStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LEAVE = "leave"
    LATE = "late"
    ON_DUTY_ELSEWHERE = "on_duty_elsewhere"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class StaffRecord:
    """A draft/confirmed staff attendance record for one staff-day."""

    record_id: str
    staff_uuid: str
    date: str
    status: StaffStatus
    assigned_session_ids: Sequence[str]
    created_at: str
    state: str = "draft"  # "draft" | "confirmed"
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[str] = None
    note: str = ""

    @property
    def is_confirmed(self) -> bool:
        return self.state == "confirmed"

    @property
    def needs_substitution(self) -> bool:
        """True when a CONFIRMED absence leaves assigned sessions uncovered."""

        absent_like = {StaffStatus.ABSENT, StaffStatus.LEAVE}
        return (
            self.is_confirmed
            and self.status in absent_like
            and bool(self.assigned_session_ids)
        )


def record_staff(
    staff_uuid: str,
    date: str,
    status: StaffStatus,
    assigned_session_ids: Optional[Sequence[str]] = None,
) -> StaffRecord:
    """Create a DRAFT staff attendance record. Not finalised."""

    assert_no_pii_identifier(staff_uuid)
    if not date:
        raise ValueError("date is required")
    return StaffRecord(
        record_id="staff_" + _uuid.uuid4().hex,
        staff_uuid=staff_uuid,
        date=date,
        status=status,
        assigned_session_ids=tuple(assigned_session_ids or ()),
        created_at=_now(),
        state="draft",
    )


def confirm_staff(
    record: StaffRecord,
    confirmed_by: str,
    note: Optional[str] = None,
) -> StaffRecord:
    """Confirm a staff record. REQUIRES a human confirmer.

    Confirmation is the gate before any substitution request can be built.
    """

    if record.is_confirmed:
        raise ValueError("staff record already confirmed; events immutable")
    if not confirmed_by or not confirmed_by.strip():
        raise ValueError("confirmation requires a human confirmer")
    assert_no_pii_identifier(confirmed_by)

    screened = record.note
    if note is not None:
        result = screen_free_text(note)
        if not result.ok:
            raise ValueError("note failed safety screen; route to review")
        screened = result.sanitized

    return replace(
        record,
        state="confirmed",
        confirmed_by=confirmed_by,
        confirmed_at=_now(),
        note=screened,
    )


def build_substitution_request(
    record: StaffRecord,
) -> Optional[SubstitutionNeededEvent]:
    """Build the substitution-ladder trigger event for a confirmed absence.

    Returns ``None`` when no substitution is needed (record not confirmed,
    staff present, or no assigned sessions). This NEVER schedules a
    substitute itself - it only asks scheduling to start its human-gated
    ladder.
    """

    if not record.needs_substitution:
        return None
    return substitution_needed_event(
        staff_uuid=record.staff_uuid,
        date=record.date,
        session_ids=record.assigned_session_ids,
        reason="staff_absent",
    )


def daily_summary(records: Sequence[StaffRecord]) -> dict:
    """Plain-language daily staff summary for an explainable surface."""

    summary = {s.value: 0 for s in StaffStatus}
    summary["draft"] = 0
    summary["needs_substitution"] = 0
    for r in records:
        summary[r.status.value] += 1
        if not r.is_confirmed:
            summary["draft"] += 1
        if r.needs_substitution:
            summary["needs_substitution"] += 1
    return summary
