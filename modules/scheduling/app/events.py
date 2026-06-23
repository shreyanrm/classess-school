"""Event emission for Scheduling & continuity (B2).

This module EMITS the operational events B2 owns:

  - ``timetable.changed``        — a timetable period was changed (only AFTER a
                                    human approved an alternative; carries the
                                    opaque approver ref).
  - ``attendance.trigger``       — a vacancy needs covering; this is the trigger
                                    the attendance/substitution flow consumes
                                    (B5 "Consumes: scheduling triggers the
                                    substitution ladder").
  - ``pacing.drift_flagged``     — a section+subject has drifted from its plan.

INVARIANTS honoured here:
  - INVARIANT 1 + 2: every event carries ONLY opaque ids (canonical_uuid, opaque
    period/section/subject/ontology ids). No builder accepts a name/email. No
    PII, ever.
  - INVARIANT 5: events are immutable + append-only. This module only APPENDS;
    it never updates or deletes. The envelope has no mutation path.
  - INVARIANT 8 / permission ladder: a ``timetable.changed`` event is only built
    with an ``approved_by`` ref present — the change it records was approved by a
    human; the emitter refuses to fabricate an approval.
  - Gateway: every cross-service write passes the gateway. With no gateway + sink
    configured, emission degrades to a clearly-labelled in-memory append-only
    sink. Direct egress is never attempted.

Envelope shape mirrors contracts/src/events/envelope.ts: attribution
(app · canonical_uuid · purpose · consent_ref) + occurred_at + a typed body.
B2's operational events use ``purpose = "operations"``. The contract's closed v1
payload union covers evidence types; these operational types ride the SAME
attributed, append-only envelope so the store, gateway, and audit treat them
identically.

Import-safe: no I/O, no provider, no secret value read at import.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from .config import SchedulingSettings, get_settings

Purpose = Literal[
    "instruction", "assessment", "mastery", "intervention",
    "operations", "communication", "account",
]

SchedulingEventType = Literal[
    "timetable.changed",
    "attendance.trigger",
    "pacing.drift_flagged",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_uuid() -> str:
    return str(uuid.uuid4())


def build_envelope(
    *,
    canonical_uuid: str,
    consent_ref: str,
    payload: dict[str, Any],
    event_type: SchedulingEventType,
    purpose: Purpose = "operations",
    app: str = "school",
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Wrap a payload in the attributed, append-only event envelope.

    Attribution = app . canonical_uuid . type . purpose . consent_ref
    (contracts/src/events/envelope). Carries ONLY opaque ids — NEVER PII.
    ``event_id`` and ``recorded_at`` would be assigned by the immutable store; we
    assign provisional values for the degraded in-memory path and let the store
    overwrite them when wired.
    """
    occurred = occurred_at or _now_iso()
    return {
        "event_id": _new_uuid(),
        "schema_version": "v1",
        "occurred_at": occurred,
        "recorded_at": occurred,
        "app": app,
        "canonical_uuid": canonical_uuid,
        "purpose": purpose,
        "consent_ref": consent_ref,
        "type": event_type,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Payload builders (opaque ids only)
# ---------------------------------------------------------------------------


def build_timetable_changed_payload(
    *,
    institution_id: str,
    period_id: str,
    section_id: str,
    change_kind: str,
    approved_by: str,
    new_teacher_ref: str | None = None,
    new_room_id: str | None = None,
    new_slot: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Payload for ``timetable.changed`` — records an APPROVED change.

    Refuses to build without ``approved_by`` (an opaque human ref): a timetable
    change is consequential and never auto-fires (INVARIANT 8). The emitter never
    fabricates an approval.
    """
    if not approved_by:
        raise PermissionError(
            "timetable.changed records a consequential, approved change and "
            "requires an approved_by ref. Scheduling never auto-commits."
        )
    payload: dict[str, Any] = {
        "institution_id": institution_id,
        "period_id": period_id,
        "section_id": section_id,
        "change_kind": change_kind,
        "approved_by": approved_by,
    }
    if new_teacher_ref is not None:
        payload["new_teacher_ref"] = new_teacher_ref
    if new_room_id is not None:
        payload["new_room_id"] = new_room_id
    if new_slot is not None:
        payload["new_slot"] = dict(new_slot)
    return payload


def build_attendance_trigger_payload(
    *,
    institution_id: str,
    period_id: str,
    section_id: str,
    on_date: str,
    reason: str,
    absent_teacher_ref: str | None = None,
) -> dict[str, Any]:
    """Payload for ``attendance.trigger`` — a vacancy needing cover.

    This is the trigger B5 consumes to start the substitution ladder. It states
    the vacancy with opaque refs only; it does NOT name a substitute (that is a
    ranked, human-approved decision downstream).
    """
    payload: dict[str, Any] = {
        "institution_id": institution_id,
        "period_id": period_id,
        "section_id": section_id,
        "on_date": on_date,
        "reason": reason,
    }
    if absent_teacher_ref is not None:
        payload["absent_teacher_ref"] = absent_teacher_ref
    return payload


def build_pacing_drift_payload(
    *,
    institution_id: str,
    section_id: str,
    subject_id: str,
    band: str,
    expected_periods: float,
    delivered_periods: int,
    drift_periods: float,
    owner_ref: str,
    owner_role: str = "coordinator",
) -> dict[str, Any]:
    """Payload for ``pacing.drift_flagged`` — a section+subject behind its plan.

    Carries the evidence (expected vs delivered), the band, and the owner — the
    explainability the proactive loop needs. PII-free.
    """
    return {
        "institution_id": institution_id,
        "section_id": section_id,
        "subject_id": subject_id,
        "band": band,
        "expected_periods": round(float(expected_periods), 2),
        "delivered_periods": int(delivered_periods),
        "drift_periods": round(float(drift_periods), 2),
        "owner_role": owner_role,
        "owner_ref": owner_ref,
    }


@dataclass
class EmittedEvent:
    """An event handed to the emitter, with its delivery status."""

    envelope: dict[str, Any]
    delivered: bool  # True only when accepted by a real sink through the gateway.
    sink: str  # human-readable sink label (degraded or gateway).


class EventEmitter:
    """Append-only emitter for B2 operational events.

    Every write passes the gateway (INVARIANT). With no gateway + sink configured
    it degrades to an in-memory append-only buffer, clearly labelled, so the
    deterministic flow works offline and tests stay green. It never deletes or
    mutates a buffered event — append-only in spirit and in code (INVARIANT 5).
    """

    def __init__(self, settings: SchedulingSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._buffer: list[dict[str, Any]] = []

    @property
    def settings(self) -> SchedulingSettings:
        return self._settings

    @property
    def degraded(self) -> bool:
        return not self._settings.has_event_sink

    @property
    def sink_label(self) -> str:
        if self.degraded:
            reasons = ", ".join(self._settings.degraded_reasons())
            return f"in-memory (degraded — set: {reasons})"
        return f"gateway sink ({self._settings.gateway_url})"

    def buffered(self) -> list[dict[str, Any]]:
        """A read-only snapshot of the append-only buffer (degraded path)."""
        return list(self._buffer)

    def emit(self, envelope: dict[str, Any]) -> EmittedEvent:
        """Emit one event. In the degraded path it is appended to the in-memory
        buffer and reported as not-delivered (so callers know it is local only).

        When a gateway sink is configured the real path would POST through the
        gateway (INVARIANT: never direct egress; the auth token is read from the
        environment by NAME, never hardcoded). That path is intentionally not
        implemented while no provider exists — the EventEmitter interface is the
        contract; the in-memory path is the supported path until the gateway is
        wired.
        """
        if self.degraded:
            self._buffer.append(envelope)
            return EmittedEvent(envelope=envelope, delivered=False, sink=self.sink_label)
        raise NotImplementedError(
            "Gateway-backed event sink is not wired yet. Configure "
            "clss.scheduling.dev.gateway_url + clss.scheduling.dev.event_sink_url "
            "and implement the gateway POST behind this method (token read from "
            "the environment by NAME, never hardcoded). Until then leave them "
            "unset to use the in-memory append-only sink."
        )

    # -- convenience end-to-end emitters -----------------------------------

    def emit_attendance_trigger(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        institution_id: str,
        period_id: str,
        section_id: str,
        on_date: str,
        reason: str,
        absent_teacher_ref: str | None = None,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_attendance_trigger_payload(
            institution_id=institution_id,
            period_id=period_id,
            section_id=section_id,
            on_date=on_date,
            reason=reason,
            absent_teacher_ref=absent_teacher_ref,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="attendance.trigger",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_pacing_drift(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        institution_id: str,
        section_id: str,
        subject_id: str,
        band: str,
        expected_periods: float,
        delivered_periods: int,
        drift_periods: float,
        owner_ref: str,
        owner_role: str = "coordinator",
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_pacing_drift_payload(
            institution_id=institution_id,
            section_id=section_id,
            subject_id=subject_id,
            band=band,
            expected_periods=expected_periods,
            delivered_periods=delivered_periods,
            drift_periods=drift_periods,
            owner_ref=owner_ref,
            owner_role=owner_role,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="pacing.drift_flagged",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_timetable_changed(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        institution_id: str,
        period_id: str,
        section_id: str,
        change_kind: str,
        approved_by: str,
        new_teacher_ref: str | None = None,
        new_room_id: str | None = None,
        new_slot: dict[str, int] | None = None,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_timetable_changed_payload(
            institution_id=institution_id,
            period_id=period_id,
            section_id=section_id,
            change_kind=change_kind,
            approved_by=approved_by,
            new_teacher_ref=new_teacher_ref,
            new_room_id=new_room_id,
            new_slot=new_slot,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="timetable.changed",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)
