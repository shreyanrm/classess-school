"""Attendance + risk events (immutable, append-only).

This module builds the event payloads emitted by the attendance domain.
Events are the ONLY way attendance state crosses a context boundary, and
every event:

- is immutable and append-only (builders return frozen dataclasses; there
  is no mutate/update path);
- carries ONLY opaque ``canonical_uuid`` references, never PII;
- passes through the gateway (this module produces payloads; transport is
  the gateway's responsibility - see :func:`to_envelope`);
- declares its ``schema_version`` so consumers can evolve safely.

One event - :class:`SubstitutionNeededEvent` - is the trigger that asks
the scheduling module to run its substitution ladder when a staff member is
recorded absent. It is a *request* event: it never auto-fires a
substitution, it asks scheduling to begin the (human-gated) ladder.

The builders here do not perform network or DB I/O, so they work offline.
Secrets used by the gateway are ENV-ONLY (see README); nothing here reads
or hardcodes a secret.
"""

from __future__ import annotations

import uuid as _uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .safety import assert_no_pii_identifier

SCHEMA_VERSION = 1
SOURCE = "attendance"


class EventType(str, Enum):
    """Event type names emitted by the attendance domain."""

    ROLL_CONFIRMED = "attendance.roll.confirmed"
    MARK_RECORDED = "attendance.mark.recorded"
    RISK_FLAGGED = "attendance.risk.flagged"
    CONFLICT_FLAGGED = "attendance.reconciliation.conflict_flagged"
    STAFF_RECORDED = "attendance.staff.recorded"
    CORRECTION_LOGGED = "attendance.correction.logged"
    SUBSTITUTION_NEEDED = "scheduling.substitution.needed"
    # Response workflow — requests a human-owned action; never auto-fires it.
    PARENT_COMM_REQUESTED = "communication.parent.requested"
    CATCHUP_PLAN_PROPOSED = "attendance.catchup_plan.proposed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event_id() -> str:
    return "evt_" + _uuid.uuid4().hex


@dataclass(frozen=True)
class _BaseEvent:
    """Common immutable event envelope fields."""

    event_id: str
    event_type: str
    occurred_at: str
    schema_version: int = SCHEMA_VERSION
    source: str = SOURCE

    def as_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (for the gateway transport)."""

        return asdict(self)


@dataclass(frozen=True)
class RollConfirmedEvent(_BaseEvent):
    session_id: str = ""
    confirmed_by: str = ""  # canonical_uuid of the human confirmer
    method: str = ""
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0


@dataclass(frozen=True)
class MarkRecordedEvent(_BaseEvent):
    session_id: str = ""
    canonical_uuid: str = ""
    status: str = ""
    method: str = ""
    confirmed_by: str = ""


@dataclass(frozen=True)
class RiskFlaggedEvent(_BaseEvent):
    canonical_uuid: str = ""
    risk_kind: str = ""  # consecutive | chronic | pattern | exam_shortage
    severity: str = ""  # watch | concern | urgent
    explanation: str = ""  # plain-language, PII-free
    window_days: int = 0
    needs_human_review: bool = True


@dataclass(frozen=True)
class ConflictFlaggedEvent(_BaseEvent):
    session_id: str = ""
    canonical_uuid: str = ""
    methods: Sequence[str] = field(default_factory=tuple)
    statuses: Sequence[str] = field(default_factory=tuple)
    needs_human_review: bool = True


@dataclass(frozen=True)
class StaffRecordedEvent(_BaseEvent):
    staff_uuid: str = ""
    status: str = ""
    date: str = ""
    confirmed_by: str = ""


@dataclass(frozen=True)
class SubstitutionNeededEvent(_BaseEvent):
    """Asks the scheduling module to start its substitution ladder.

    This is a request, not an action. Scheduling owns the ladder and the
    human-approval gate; this event only signals that a slot is uncovered.
    """

    staff_uuid: str = ""
    date: str = ""
    session_ids: Sequence[str] = field(default_factory=tuple)
    reason: str = "staff_absent"


@dataclass(frozen=True)
class CorrectionLoggedEvent(_BaseEvent):
    """A post-finalisation correction to an already-locked roll.

    Emitted by the locked-correction flow. The correction itself is a NEW,
    append-only record (the original finalised mark is never overwritten); this
    event carries the audit trail — who, when, why, and the before/after status.
    """

    session_id: str = ""
    canonical_uuid: str = ""
    previous_status: str = ""
    corrected_status: str = ""
    corrected_by: str = ""  # canonical_uuid of the authorising human
    reason: str = ""        # plain-language, PII-screened


@dataclass(frozen=True)
class ParentCommunicationRequestedEvent(_BaseEvent):
    """Asks the communication module to reach a guardian about absence.

    A REQUEST, never a sent message: communication owns delivery, consent/
    language, and the human-approval gate. This only signals that repeated
    absence warrants contact. PII-free — the guardian is resolved downstream
    from the opaque learner ref under consent.
    """

    canonical_uuid: str = ""
    risk_kind: str = ""
    severity: str = ""
    reason: str = ""  # plain-language, PII-free
    requires_approval: bool = True


@dataclass(frozen=True)
class CatchupPlanProposedEvent(_BaseEvent):
    """A proposed catch-up plan after repeated absence.

    A proposal a human reviews and owns; missed sessions/topics are listed so a
    teacher can confirm the recovery steps. Never auto-assigned.
    """

    canonical_uuid: str = ""
    missed_sessions: int = 0
    subjects: Sequence[str] = field(default_factory=tuple)
    requires_approval: bool = True


# --- builders --------------------------------------------------------------


def roll_confirmed_event(
    session_id: str,
    confirmed_by: str,
    method: str,
    counts: Mapping[str, int],
) -> RollConfirmedEvent:
    assert_no_pii_identifier(confirmed_by)
    return RollConfirmedEvent(
        event_id=_event_id(),
        event_type=EventType.ROLL_CONFIRMED.value,
        occurred_at=_now(),
        session_id=session_id,
        confirmed_by=confirmed_by,
        method=method,
        present=int(counts.get("present", 0)),
        absent=int(counts.get("absent", 0)),
        late=int(counts.get("late", 0)),
        excused=int(counts.get("excused", 0)),
    )


def mark_recorded_event(
    session_id: str,
    canonical_uuid: str,
    status: str,
    method: str,
    confirmed_by: str,
) -> MarkRecordedEvent:
    assert_no_pii_identifier(canonical_uuid)
    assert_no_pii_identifier(confirmed_by)
    return MarkRecordedEvent(
        event_id=_event_id(),
        event_type=EventType.MARK_RECORDED.value,
        occurred_at=_now(),
        session_id=session_id,
        canonical_uuid=canonical_uuid,
        status=status,
        method=method,
        confirmed_by=confirmed_by,
    )


def risk_flagged_event(
    canonical_uuid: str,
    risk_kind: str,
    severity: str,
    explanation: str,
    window_days: int,
) -> RiskFlaggedEvent:
    assert_no_pii_identifier(canonical_uuid)
    return RiskFlaggedEvent(
        event_id=_event_id(),
        event_type=EventType.RISK_FLAGGED.value,
        occurred_at=_now(),
        canonical_uuid=canonical_uuid,
        risk_kind=risk_kind,
        severity=severity,
        explanation=explanation,
        window_days=window_days,
        needs_human_review=True,
    )


def conflict_flagged_event(
    session_id: str,
    canonical_uuid: str,
    methods: Sequence[str],
    statuses: Sequence[str],
) -> ConflictFlaggedEvent:
    assert_no_pii_identifier(canonical_uuid)
    return ConflictFlaggedEvent(
        event_id=_event_id(),
        event_type=EventType.CONFLICT_FLAGGED.value,
        occurred_at=_now(),
        session_id=session_id,
        canonical_uuid=canonical_uuid,
        methods=tuple(methods),
        statuses=tuple(statuses),
        needs_human_review=True,
    )


def staff_recorded_event(
    staff_uuid: str,
    status: str,
    date: str,
    confirmed_by: str,
) -> StaffRecordedEvent:
    assert_no_pii_identifier(staff_uuid)
    assert_no_pii_identifier(confirmed_by)
    return StaffRecordedEvent(
        event_id=_event_id(),
        event_type=EventType.STAFF_RECORDED.value,
        occurred_at=_now(),
        staff_uuid=staff_uuid,
        status=status,
        date=date,
        confirmed_by=confirmed_by,
    )


def substitution_needed_event(
    staff_uuid: str,
    date: str,
    session_ids: Sequence[str],
    reason: str = "staff_absent",
) -> SubstitutionNeededEvent:
    """Build the event that triggers the scheduling substitution ladder."""

    assert_no_pii_identifier(staff_uuid)
    return SubstitutionNeededEvent(
        event_id=_event_id(),
        event_type=EventType.SUBSTITUTION_NEEDED.value,
        occurred_at=_now(),
        staff_uuid=staff_uuid,
        date=date,
        session_ids=tuple(session_ids),
        reason=reason,
    )


def correction_logged_event(
    session_id: str,
    canonical_uuid: str,
    previous_status: str,
    corrected_status: str,
    corrected_by: str,
    reason: str,
) -> CorrectionLoggedEvent:
    """Audit event for a post-finalisation locked correction."""

    assert_no_pii_identifier(canonical_uuid)
    assert_no_pii_identifier(corrected_by)
    return CorrectionLoggedEvent(
        event_id=_event_id(),
        event_type=EventType.CORRECTION_LOGGED.value,
        occurred_at=_now(),
        session_id=session_id,
        canonical_uuid=canonical_uuid,
        previous_status=previous_status,
        corrected_status=corrected_status,
        corrected_by=corrected_by,
        reason=reason,
    )


def parent_communication_requested_event(
    canonical_uuid: str,
    risk_kind: str,
    severity: str,
    reason: str,
) -> ParentCommunicationRequestedEvent:
    """Request guardian contact about absence. requires_approval is always True."""

    assert_no_pii_identifier(canonical_uuid)
    return ParentCommunicationRequestedEvent(
        event_id=_event_id(),
        event_type=EventType.PARENT_COMM_REQUESTED.value,
        occurred_at=_now(),
        canonical_uuid=canonical_uuid,
        risk_kind=risk_kind,
        severity=severity,
        reason=reason,
        requires_approval=True,
    )


def catchup_plan_proposed_event(
    canonical_uuid: str,
    missed_sessions: int,
    subjects: Sequence[str],
) -> CatchupPlanProposedEvent:
    """Propose a catch-up plan. requires_approval is always True."""

    assert_no_pii_identifier(canonical_uuid)
    return CatchupPlanProposedEvent(
        event_id=_event_id(),
        event_type=EventType.CATCHUP_PLAN_PROPOSED.value,
        occurred_at=_now(),
        canonical_uuid=canonical_uuid,
        missed_sessions=int(missed_sessions),
        subjects=tuple(subjects),
        requires_approval=True,
    )


def to_envelope(event: _BaseEvent) -> Dict[str, Any]:
    """Wrap an event for gateway transport.

    The gateway (not this module) signs and routes the envelope. This
    helper only normalises the shape and is offline-safe.
    """

    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "schema_version": event.schema_version,
        "source": event.source,
        "occurred_at": event.occurred_at,
        "payload": event.as_dict(),
    }


def collect_append_only(
    log: List[Dict[str, Any]], event: _BaseEvent
) -> List[Dict[str, Any]]:
    """Append an event envelope to an in-memory log (append-only).

    Returns a NEW list; the input log is never mutated in place, modelling
    the append-only, immutable event stream.
    """

    return [*log, to_envelope(event)]
