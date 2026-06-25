"""Event emission for Relationships & communication (B9).

This module EMITS the operational events B9 owns:

  - ``message.sent``            — a message entered a monitored channel (carries
                                  the safety verdict + opaque refs; NEVER the
                                  message text — text stays in the monitored
                                  store, only its safety classification rides the
                                  event).
  - ``meeting.scheduled``       — a parent–teacher (or care) meeting was set, with
                                  opaque participant refs and a partnership
                                  purpose.
  - ``sentiment.observed``      — a coarse, opaque sentiment/wellbeing signal was
                                  observed on a surface (a band, never a score for
                                  a person; evidence for the proactive loop).
  - ``safeguarding.escalated``  — a child-safety escalation was routed to a
                                  qualified human (the auditable record that a
                                  person was brought in; opaque refs only).
  - ``ptm.scheduled``           — a parent–teacher meeting was BOOKED (the
                                  permission-gated, human-approved booking; opaque
                                  participant refs + a partnership purpose).
  - ``ptm.completed``           — a PTM finished and produced a shared action
                                  plan (opaque refs + how many actions were
                                  agreed; never the conversation text).
  - ``action.assigned``         — a tracked task / agreed action was given a human
                                  owner (the auditable record that the system
                                  prepared and a person OWNED it; opaque refs).

INVARIANTS honoured here:
  - INVARIANT 1 + 2: every event carries ONLY opaque ids (canonical_uuid, opaque
    context/meeting/surface ids). No builder accepts a name/email. The message
    BODY is never put on an event — only its safety classification. No PII, ever.
  - INVARIANT 5: events are immutable + append-only. This module only APPENDS;
    it never updates or deletes. The envelope has no mutation path.
  - CHILD-SAFETY: ``message.sent`` carries the safety verdict so the audit trail
    proves every free-text message was screened; ``safeguarding.escalated``
    records that a qualified human was routed in.
  - Gateway: every cross-service write passes the gateway. With no gateway + sink
    configured, emission degrades to a clearly-labelled in-memory append-only
    sink. Direct egress is never attempted.

Envelope shape mirrors contracts/src/events/envelope.ts: attribution
(app · canonical_uuid · purpose · consent_ref) + occurred_at + a typed body.
B9's events use ``purpose = "communication"`` (and ``intervention`` for a
safeguarding escalation). These types ride the SAME attributed, append-only
envelope so the store, gateway, and audit treat them identically.

Import-safe: no I/O, no provider, no secret value read at import.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from .config import CommunicationSettings, get_settings

Purpose = Literal[
    "instruction", "assessment", "mastery", "intervention",
    "operations", "communication", "account",
]

CommunicationEventType = Literal[
    "message.sent",
    "meeting.scheduled",
    "sentiment.observed",
    "safeguarding.escalated",
    "ptm.scheduled",
    "ptm.completed",
    "action.assigned",
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
    event_type: CommunicationEventType,
    purpose: Purpose = "communication",
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
# Payload builders (opaque ids only — and NEVER message text)
# ---------------------------------------------------------------------------

# A guard against ever putting message text (or PII) on an event payload.
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {"name", "email", "phone", "first_name", "last_name", "dob", "body", "text", "message"}
)


def _assert_payload_safe(payload: dict[str, Any]) -> None:
    leaked = _FORBIDDEN_PAYLOAD_KEYS & set(payload.keys())
    if leaked:
        raise ValueError(
            f"Event payload would carry forbidden keys {sorted(leaked)} (PII or "
            "message body). Events carry only opaque ids + classifications."
        )


def build_message_sent_payload(
    *,
    surface: str,
    context_ref: str,
    sender_ref: str,
    safety_severity: str,
    flagged: bool,
    screened: bool = True,
) -> dict[str, Any]:
    """Payload for ``message.sent`` — records that a message was screened + sent.

    Carries the SAFETY VERDICT (severity, flagged, screened) and opaque refs —
    NEVER the message body. ``screened`` is asserted True: there is no
    unmonitored channel, so an event for an unscreened message is a defect.
    """
    if not screened:
        raise ValueError(
            "Refusing to emit message.sent for an UNSCREENED message. Every "
            "free-text message passes child-safety; there are no unmonitored "
            "channels."
        )
    payload = {
        "surface": surface,
        "context_ref": context_ref,
        "sender_ref": sender_ref,
        "safety_severity": safety_severity,
        "flagged": bool(flagged),
        "screened": True,
    }
    _assert_payload_safe(payload)
    return payload


def build_meeting_scheduled_payload(
    *,
    meeting_id: str,
    context_ref: str,
    participant_refs: list[str],
    purpose_label: str,
    scheduled_for: str,
) -> dict[str, Any]:
    """Payload for ``meeting.scheduled`` — a partnership/care meeting was set.

    Opaque participant refs only; ``purpose_label`` is a partnership-shaped
    label (e.g. "parent_teacher_partnership"), never surveillance.
    """
    payload = {
        "meeting_id": meeting_id,
        "context_ref": context_ref,
        "participant_refs": list(participant_refs),
        "purpose_label": purpose_label,
        "scheduled_for": scheduled_for,
    }
    _assert_payload_safe(payload)
    return payload


def build_sentiment_observed_payload(
    *,
    surface: str,
    context_ref: str,
    band: str,
    evidence: str,
) -> dict[str, Any]:
    """Payload for ``sentiment.observed`` — a coarse wellbeing BAND, never a
    per-person score. Carries the evidence the proactive loop needs."""
    payload = {
        "surface": surface,
        "context_ref": context_ref,
        "band": band,          # e.g. "positive" / "neutral" / "needs_attention".
        "evidence": evidence,  # a short, non-PII rationale.
    }
    _assert_payload_safe(payload)
    return payload


def build_safeguarding_escalated_payload(
    *,
    surface: str,
    writer_ref: str,
    severity: str,
    categories: list[str],
    owner_role: str,
    is_crisis: bool,
) -> dict[str, Any]:
    """Payload for ``safeguarding.escalated`` — a child-safety escalation routed
    to a qualified human. Carries the verdict + the human owner role, NEVER the
    text. This is the auditable proof that a person was brought in."""
    payload = {
        "surface": surface,
        "writer_ref": writer_ref,
        "severity": severity,
        "categories": list(categories),
        "owner_role": owner_role,
        "is_crisis": bool(is_crisis),
        "routed_to_human": True,
    }
    _assert_payload_safe(payload)
    return payload


def build_ptm_scheduled_payload(
    *,
    meeting_id: str,
    context_ref: str,
    participant_refs: list[str],
    scheduled_for: str,
    approved: bool,
) -> dict[str, Any]:
    """Payload for ``ptm.scheduled`` — a parent–teacher meeting was BOOKED.

    Booking is a consequential action on the permission ladder; ``approved`` is
    asserted True (a booking that was never approved is a defect — the system
    prepares, a human confirms). Opaque refs only; partnership-shaped purpose.
    """
    if not approved:
        raise ValueError(
            "Refusing to emit ptm.scheduled for an UNAPPROVED booking. Booking a "
            "meeting is consequential and is confirmed by a human before it is "
            "real (permission ladder)."
        )
    payload = {
        "meeting_id": meeting_id,
        "context_ref": context_ref,
        "participant_refs": list(participant_refs),
        "purpose_label": "parent_teacher_partnership",
        "scheduled_for": scheduled_for,
        "approved": True,
    }
    _assert_payload_safe(payload)
    return payload


def build_ptm_completed_payload(
    *,
    meeting_id: str,
    context_ref: str,
    action_count: int,
    had_consented_capture: bool,
) -> dict[str, Any]:
    """Payload for ``ptm.completed`` — a PTM finished + produced a shared plan.

    Carries how many actions were agreed and whether capture was consented —
    NEVER the conversation text (that stays in the meeting record)."""
    payload = {
        "meeting_id": meeting_id,
        "context_ref": context_ref,
        "action_count": int(action_count),
        "had_consented_capture": bool(had_consented_capture),
    }
    _assert_payload_safe(payload)
    return payload


def build_action_assigned_payload(
    *,
    task_id: str,
    context_ref: str,
    owner_ref: str,
    owner_role: str,
    source: str,
    assigned_by_ref: str,
) -> dict[str, Any]:
    """Payload for ``action.assigned`` — a tracked task got a human OWNER.

    The auditable proof that the system prepared a task and a PERSON owned it
    (``assigned_by_ref``) — nothing auto-assigns. Opaque refs only; ``source``
    is a label such as ``message`` or ``ptm`` (never any text)."""
    if not owner_ref:
        raise ValueError(
            "Refusing to emit action.assigned with no owner. An action is always "
            "owned by a human (owner_ref); the system never owns a task itself."
        )
    if not assigned_by_ref:
        raise ValueError(
            "Refusing to emit action.assigned with no human assigner. Assigning an "
            "owner is a human act on the permission ladder; it never auto-fires."
        )
    payload = {
        "task_id": task_id,
        "context_ref": context_ref,
        "owner_ref": owner_ref,
        "owner_role": owner_role,
        "source": source,
        "assigned_by_ref": assigned_by_ref,
    }
    _assert_payload_safe(payload)
    return payload


@dataclass
class EmittedEvent:
    """An event handed to the emitter, with its delivery status."""

    envelope: dict[str, Any]
    delivered: bool  # True only when accepted by a real sink through the gateway.
    sink: str        # human-readable sink label (degraded or gateway).


class EventEmitter:
    """Append-only emitter for B9 operational events.

    Every write passes the gateway (INVARIANT). With no gateway + sink configured
    it degrades to an in-memory append-only buffer, clearly labelled, so the
    deterministic flow works offline and tests stay green. It never deletes or
    mutates a buffered event — append-only in spirit and in code (INVARIANT 5).
    """

    def __init__(self, settings: CommunicationSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._buffer: list[dict[str, Any]] = []

    @property
    def settings(self) -> CommunicationSettings:
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
            "clss.communication.dev.gateway_url + clss.communication.dev.event_sink_url "
            "and implement the gateway POST behind this method (token read from "
            "the environment by NAME, never hardcoded). Until then leave them "
            "unset to use the in-memory append-only sink."
        )

    # -- convenience end-to-end emitters -----------------------------------

    def emit_message_sent(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        surface: str,
        context_ref: str,
        sender_ref: str,
        safety_severity: str,
        flagged: bool,
        screened: bool = True,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_message_sent_payload(
            surface=surface,
            context_ref=context_ref,
            sender_ref=sender_ref,
            safety_severity=safety_severity,
            flagged=flagged,
            screened=screened,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="message.sent",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_meeting_scheduled(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        meeting_id: str,
        context_ref: str,
        participant_refs: list[str],
        purpose_label: str,
        scheduled_for: str,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_meeting_scheduled_payload(
            meeting_id=meeting_id,
            context_ref=context_ref,
            participant_refs=participant_refs,
            purpose_label=purpose_label,
            scheduled_for=scheduled_for,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="meeting.scheduled",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_sentiment_observed(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        surface: str,
        context_ref: str,
        band: str,
        evidence: str,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_sentiment_observed_payload(
            surface=surface,
            context_ref=context_ref,
            band=band,
            evidence=evidence,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="sentiment.observed",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_safeguarding_escalated(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        surface: str,
        writer_ref: str,
        severity: str,
        categories: list[str],
        owner_role: str,
        is_crisis: bool,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_safeguarding_escalated_payload(
            surface=surface,
            writer_ref=writer_ref,
            severity=severity,
            categories=categories,
            owner_role=owner_role,
            is_crisis=is_crisis,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="safeguarding.escalated",
            purpose="intervention",  # a safeguarding escalation is an intervention.
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_ptm_scheduled(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        meeting_id: str,
        context_ref: str,
        participant_refs: list[str],
        scheduled_for: str,
        approved: bool,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_ptm_scheduled_payload(
            meeting_id=meeting_id,
            context_ref=context_ref,
            participant_refs=participant_refs,
            scheduled_for=scheduled_for,
            approved=approved,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="ptm.scheduled",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_ptm_completed(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        meeting_id: str,
        context_ref: str,
        action_count: int,
        had_consented_capture: bool,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_ptm_completed_payload(
            meeting_id=meeting_id,
            context_ref=context_ref,
            action_count=action_count,
            had_consented_capture=had_consented_capture,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="ptm.completed",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_action_assigned(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        task_id: str,
        context_ref: str,
        owner_ref: str,
        owner_role: str,
        source: str,
        assigned_by_ref: str,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_action_assigned_payload(
            task_id=task_id,
            context_ref=context_ref,
            owner_ref=owner_ref,
            owner_role=owner_role,
            source=source,
            assigned_by_ref=assigned_by_ref,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="action.assigned",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)
