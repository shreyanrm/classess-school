"""The event seam for the FLUID bridge (spine A6).

Inbound learning activity (xAPI / Caliper) becomes attributed, PII-free events
appended to the immutable, append-only event store (INVARIANT 5). This module
builds the *attributed event input* in the event contract's shape and hands it
to an injected emitter that posts THROUGH THE GATEWAY (INVARIANT 3). This
package holds no event-store credentials and performs no direct write.

Every event carries the opaque ``canonical_uuid``, a ``purpose`` and a
``consent_ref`` — CONSENT gates the write (INVARIANT 6). With no consent_ref the
builder refuses to construct the event rather than emit an unattributed one.

Events are produced, never mutated; this module exposes only build + emit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Protocol

from .models import (
    CanonicalRef,
    LearningActivityStatement,
    Verb,
    assert_no_pii,
)

# The integration bridge runs under the "platform" app context when relaying
# external activity; the originating standard is recorded in the payload.
BRIDGE_APP = "platform"

# Map the bridge's neutral verbs to event-contract types. ANSWERED/SCORED carry
# evidence; the rest are activity signals recorded as attempts with no score.
_VERB_TO_EVENT_TYPE: dict[Verb, str] = {
    Verb.ANSWERED: "attempt.recorded",
    Verb.SCORED: "attempt.recorded",
    Verb.SUBMITTED: "submission.created",
    Verb.STARTED: "attempt.recorded",
    Verb.COMPLETED: "attempt.recorded",
    Verb.VIEWED: "attempt.recorded",
    Verb.PROGRESSED: "attempt.recorded",
}


class EmitRefused(ValueError):
    """Raised when an event cannot be built/emitted under the invariants."""


class EventEmitter(Protocol):
    """Posts an attributed event input to the event store THROUGH THE GATEWAY.

    The real implementation is an authenticated HTTP call to the gateway route
    for ``POST /v1/events``. It returns the stored event id (or raises). This
    package injects it so the bridge never holds credentials.
    """

    def emit(self, event_input: dict[str, Any]) -> str: ...


@dataclass(frozen=True)
class ActivityEventContext:
    """The non-identifying attribution context for a relayed activity event."""

    purpose: str  # one of the event-contract purposes, e.g. "instruction"
    consent_ref: str  # the consent record the relay is captured under
    app: str = BRIDGE_APP


def build_activity_event(
    statement: LearningActivityStatement,
    context: ActivityEventContext,
    *,
    source_standard: str,
) -> dict[str, Any]:
    """Build an attributed, PII-free event input from an activity statement.

    Shape mirrors the event-store ``EmitEventInput`` contract:
    ``{app, canonical_uuid, purpose, consent_ref, occurred_at, type, payload}``.
    """

    if not context.consent_ref:
        raise EmitRefused("consent_ref is required — consent gates every write.")
    if statement.actor.canonical_uuid is None:
        raise EmitRefused(
            "actor must resolve to a canonical_uuid before relaying as an event."
        )

    event_type = _VERB_TO_EVENT_TYPE.get(statement.verb, "attempt.recorded")

    payload: dict[str, Any] = {
        "source_standard": source_standard,
        "verb": statement.verb.value,
        "object_id": statement.object_id,
        "object_type": statement.object_type,
        "context_activity_ids": list(statement.context_activity_ids),
    }
    if statement.result_success is not None:
        payload["correct"] = statement.result_success
    if statement.result_score_scaled is not None:
        payload["score_scaled"] = statement.result_score_scaled
    if statement.result_completion is not None:
        payload["completion"] = statement.result_completion
    if statement.extensions:
        payload["extensions"] = dict(statement.extensions)

    event_input: dict[str, Any] = {
        "app": context.app,
        "canonical_uuid": statement.actor.canonical_uuid,
        "purpose": context.purpose,
        "consent_ref": context.consent_ref,
        "occurred_at": _iso(statement.timestamp),
        "type": event_type,
        "payload": payload,
    }

    # Hard backstop: no PII may ride along on a relayed event (INVARIANT 1/2).
    assert_no_pii(event_input, where="activity event input")
    return event_input


def emit_activity(
    statement: LearningActivityStatement,
    context: ActivityEventContext,
    *,
    source_standard: str,
    emitter: EventEmitter | None = None,
) -> dict[str, Any]:
    """Build then (if an emitter is injected) emit an activity event.

    Returns a result dict with the built ``event`` and either the stored
    ``event_id`` or ``degraded: True`` when no emitter is wired (offline mode).
    """

    event = build_activity_event(statement, context, source_standard=source_standard)
    if emitter is None:
        return {"event": event, "event_id": None, "degraded": True}
    event_id = emitter.emit(event)
    return {"event": event, "event_id": event_id, "degraded": False}


def _iso(ts: datetime) -> str:
    return ts.isoformat()


__all__ = [
    "BRIDGE_APP",
    "EmitRefused",
    "EventEmitter",
    "ActivityEventContext",
    "build_activity_event",
    "emit_activity",
]
