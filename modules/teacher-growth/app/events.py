"""Event emission for Teacher growth (B10).

B10 EMITS coaching-signal events — and they are MARKED PRIVATE. The build
breakdown is explicit: B10 "Emits: coaching-signal events (private)." Privacy is
not a comment here; it is a field on the envelope (``private = True``,
``visibility = "teacher_first"``) and a refusal in the emitter to build an event
that claims to be anything else.

Event types emitted:
  - ``coaching.signal_generated`` — a private coaching reflection was produced for
                                    a teacher's own lesson.
  - ``growth.plan_updated`` — a teacher's PRIVATE development plan was (re)built
                              from their own signals over time (also private +
                              teacher-first; carries a trajectory shape, never a
                              score, rank, or another teacher's data).
  - ``quality.review_signed_off`` — a HUMAN reviewer signed off a quality review
                                    (carries the opaque reviewer ref; refuses to
                                    build without one — INVARIANT 8).
  - ``continuity.handover_recorded`` — a knowledge-transfer note was handed over.

INVARIANTS honoured here:
  - INVARIANT 1 + 2: every event carries ONLY opaque ids (canonical_uuid, opaque
    teacher/reviewer/section/subject/lesson ids). No builder accepts a name/email.
  - INVARIANT 5: events are immutable + append-only. This module only APPENDS; it
    never updates or deletes. The envelope has no mutation path.
  - INVARIANT 6 (consent / private read): coaching-signal events are stamped
    private + teacher_first, so a downstream reader cannot treat them as open.
  - INVARIANT 8 (permission ladder): a ``quality.review_signed_off`` event is only
    built with a human ``signed_off_by`` ref; the emitter never fabricates one.
  - Gateway: every cross-service write passes the gateway. With no gateway + sink
    configured, emission degrades to a clearly-labelled in-memory append-only
    sink. Direct egress is never attempted.

Envelope shape mirrors the platform event contract: attribution (app ·
canonical_uuid · purpose · consent_ref) + occurred_at + a typed body, plus the
B10 privacy stamp. Import-safe: no I/O, no provider, no secret value at import.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from .config import TeacherGrowthSettings, get_settings

Purpose = Literal[
    "instruction", "assessment", "mastery", "intervention",
    "operations", "communication", "account", "growth",
]

TeacherGrowthEventType = Literal[
    "coaching.signal_generated",
    "growth.plan_updated",
    "quality.review_signed_off",
    "continuity.handover_recorded",
]

# B10 event types that are ALWAYS private + teacher-first, regardless of caller.
# A development-plan update is just as private as a coaching signal.
_PRIVATE_TYPES: frozenset[str] = frozenset(
    {"coaching.signal_generated", "growth.plan_updated"}
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_uuid() -> str:
    return str(uuid.uuid4())


def build_envelope(
    *,
    canonical_uuid: str,
    consent_ref: str,
    payload: dict[str, Any],
    event_type: TeacherGrowthEventType,
    purpose: Purpose = "growth",
    app: str = "school",
    occurred_at: str | None = None,
    private: bool = False,
    visibility: str = "scoped",
) -> dict[str, Any]:
    """Wrap a payload in the attributed, append-only event envelope.

    Carries ONLY opaque ids — NEVER PII. ``event_id`` and ``recorded_at`` would be
    assigned by the immutable store; provisional values are set for the degraded
    in-memory path and the store overwrites them when wired.

    Coaching-signal events are FORCED private + teacher_first here so no caller can
    accidentally emit a public coaching event.
    """
    if event_type in _PRIVATE_TYPES:
        private = True
        visibility = "teacher_first"
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
        "private": private,
        "visibility": visibility,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# Payload builders (opaque ids only)
# ---------------------------------------------------------------------------


def build_coaching_signal_payload(
    *,
    teacher_ref: str,
    lesson_id: str,
    dimension: str,
    direction: str,
    confidence: str,
) -> dict[str, Any]:
    """Payload for ``coaching.signal_generated`` — a private reflection produced.

    Carries the dimension, the growth direction, and the confidence band — never
    the free-text reading (kept out of the event so the private detail stays with
    the teacher), and never a score or rank.
    """
    return {
        "teacher_ref": teacher_ref,
        "lesson_id": lesson_id,
        "dimension": dimension,
        "direction": direction,
        "confidence": confidence,
        "private": True,
        "visibility": "teacher_first",
    }


def build_plan_updated_payload(
    *,
    teacher_ref: str,
    lessons_observed: int,
    focus_dimensions: list[str],
) -> dict[str, Any]:
    """Payload for ``growth.plan_updated`` — a private development plan changed.

    Carries the coverage (how many lessons informed the plan) and the dimensions
    currently in focus — the *shape* only. It never carries the free-text plan,
    a per-dimension trajectory verdict for another reader to grade, a score, or a
    rank. The detail stays in the teacher's private plan.
    """
    return {
        "teacher_ref": teacher_ref,
        "lessons_observed": lessons_observed,
        "focus_dimensions": list(focus_dimensions),
        "private": True,
        "visibility": "teacher_first",
    }


def build_review_signed_off_payload(
    *,
    review_id: str,
    teacher_ref: str,
    cycle: str,
    signed_off_by: str,
) -> dict[str, Any]:
    """Payload for ``quality.review_signed_off`` — records a HUMAN sign-off.

    Refuses to build without ``signed_off_by`` (an opaque human reviewer ref): a
    quality review is consequential and never auto-finalises (INVARIANT 8).
    """
    if not signed_off_by:
        raise PermissionError(
            "quality.review_signed_off records a consequential human sign-off and "
            "requires a signed_off_by ref. Reviews never auto-close."
        )
    return {
        "review_id": review_id,
        "teacher_ref": teacher_ref,
        "cycle": cycle,
        "signed_off_by": signed_off_by,
    }


def build_handover_recorded_payload(
    *,
    section_id: str,
    subject_id: str,
    from_teacher_ref: str,
    reason: str,
    current_topic_id: str,
    to_teacher_ref: str | None = None,
    carries_coaching: bool = False,
) -> dict[str, Any]:
    """Payload for ``continuity.handover_recorded`` — a handover note was passed."""
    payload: dict[str, Any] = {
        "section_id": section_id,
        "subject_id": subject_id,
        "from_teacher_ref": from_teacher_ref,
        "reason": reason,
        "current_topic_id": current_topic_id,
        "carries_coaching": carries_coaching,
    }
    if to_teacher_ref is not None:
        payload["to_teacher_ref"] = to_teacher_ref
    return payload


@dataclass
class EmittedEvent:
    """An event handed to the emitter, with its delivery status."""

    envelope: dict[str, Any]
    delivered: bool  # True only when accepted by a real sink through the gateway.
    sink: str  # human-readable sink label (degraded or gateway).


class EventEmitter:
    """Append-only emitter for B10 growth events.

    Every write passes the gateway (INVARIANT). With no gateway + sink configured
    it degrades to an in-memory append-only buffer, clearly labelled, so the
    deterministic flow works offline and tests stay green. It never deletes or
    mutates a buffered event — append-only in spirit and in code (INVARIANT 5).
    """

    def __init__(self, settings: TeacherGrowthSettings | None = None) -> None:
        self._settings = settings or get_settings()
        self._buffer: list[dict[str, Any]] = []

    @property
    def settings(self) -> TeacherGrowthSettings:
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
            "clss.teachergrowth.dev.gateway_url + "
            "clss.teachergrowth.dev.event_sink_url and implement the gateway POST "
            "behind this method (token read from the environment by NAME, never "
            "hardcoded). Until then leave them unset to use the in-memory "
            "append-only sink."
        )

    # -- convenience end-to-end emitters -----------------------------------

    def emit_coaching_signal(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        teacher_ref: str,
        lesson_id: str,
        dimension: str,
        direction: str,
        confidence: str,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_coaching_signal_payload(
            teacher_ref=teacher_ref,
            lesson_id=lesson_id,
            dimension=dimension,
            direction=direction,
            confidence=confidence,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="coaching.signal_generated",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_plan_updated(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        teacher_ref: str,
        lessons_observed: int,
        focus_dimensions: list[str],
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_plan_updated_payload(
            teacher_ref=teacher_ref,
            lessons_observed=lessons_observed,
            focus_dimensions=focus_dimensions,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="growth.plan_updated",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_review_signed_off(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        review_id: str,
        teacher_ref: str,
        cycle: str,
        signed_off_by: str,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_review_signed_off_payload(
            review_id=review_id,
            teacher_ref=teacher_ref,
            cycle=cycle,
            signed_off_by=signed_off_by,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="quality.review_signed_off",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)

    def emit_handover_recorded(
        self,
        *,
        canonical_uuid: str,
        consent_ref: str,
        section_id: str,
        subject_id: str,
        from_teacher_ref: str,
        reason: str,
        current_topic_id: str,
        to_teacher_ref: str | None = None,
        carries_coaching: bool = False,
        occurred_at: str | None = None,
    ) -> EmittedEvent:
        payload = build_handover_recorded_payload(
            section_id=section_id,
            subject_id=subject_id,
            from_teacher_ref=from_teacher_ref,
            reason=reason,
            current_topic_id=current_topic_id,
            to_teacher_ref=to_teacher_ref,
            carries_coaching=carries_coaching,
        )
        envelope = build_envelope(
            canonical_uuid=canonical_uuid,
            consent_ref=consent_ref,
            payload=payload,
            event_type="continuity.handover_recorded",
            occurred_at=occurred_at,
        )
        return self.emit(envelope)
