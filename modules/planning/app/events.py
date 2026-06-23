"""Immutable, append-only planning events.

Invariants honored here:
  * Events are immutable + append-only (frozen dataclasses; the log never mutates
    or deletes an existing record).
  * Behavioral payloads carry ONLY an opaque ``canonical_uuid`` — never PII. A
    runtime guard rejects keys that look like personal identifiers.
  * Every event records the gateway context it passed through so downstream
    consumers can prove the "every call passes the gateway" invariant.

No network, no DB. The default log is an in-memory append-only list; callers may
inject a sink callable (e.g. a gateway publisher) for production wiring.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple


class EventType(str, Enum):
    """Closed vocabulary of d6 planning events."""

    PLAN_DRAFTED = "planning.plan.drafted"
    PLAN_ADAPTED = "planning.plan.adapted"
    PLAN_OUTCOME_MAPPED = "planning.plan.outcome_mapped"
    DIFFERENTIATION_GENERATED = "planning.differentiation.generated"
    DIARY_PLANNED = "planning.diary.planned"
    DIARY_DELIVERED = "planning.diary.delivered"
    DIARY_PARTIAL = "planning.diary.partial"
    PACING_SIGNAL_EMITTED = "planning.pacing.signal_emitted"


# Substrings that, if present in a payload key, indicate possible PII. Behavioral
# data must reference learners/teachers only by opaque canonical_uuid.
_PII_KEY_HINTS: Tuple[str, ...] = (
    "name",
    "email",
    "phone",
    "address",
    "dob",
    "birth",
    "aadhaar",
    "ssn",
    "guardian",
    "parent_contact",
    "first_name",
    "last_name",
    "full_name",
)

# Keys that legitimately end in a hint substring but are NOT PII.
_PII_KEY_ALLOW: Tuple[str, ...] = (
    "outcome_name_key",  # ontology slug, not a person
    "band_name",         # mastery band label
)


class PiiInPayloadError(ValueError):
    """Raised when an event payload appears to contain PII."""


def _assert_no_pii(payload: Mapping[str, Any]) -> None:
    for key in payload:
        lowered = str(key).lower()
        if lowered in _PII_KEY_ALLOW:
            continue
        for hint in _PII_KEY_HINTS:
            if hint in lowered:
                raise PiiInPayloadError(
                    f"event payload key {key!r} looks like PII; behavioral data "
                    "must reference subjects by canonical_uuid only"
                )


@dataclass(frozen=True)
class PlanningEvent:
    """A single immutable planning event.

    ``subject_uuid`` is the opaque canonical_uuid the event is about (a learner,
    a class, a plan). It is never a name or other PII.
    """

    event_type: EventType
    subject_uuid: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    gateway_context: str = "clss.gateway"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.subject_uuid:
            raise ValueError("subject_uuid is required and must be a canonical_uuid")
        _assert_no_pii(self.payload)
        # Freeze the payload into an immutable mapping snapshot.
        object.__setattr__(self, "payload", dict(self.payload))

    def to_record(self) -> Dict[str, Any]:
        """Serialize for an append-only sink (gateway / event store)."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "subject_uuid": self.subject_uuid,
            "payload": dict(self.payload),
            "gateway_context": self.gateway_context,
            "occurred_at": self.occurred_at,
        }


class EventLog:
    """Append-only event log.

    The log exposes append + read; it intentionally provides no update or delete.
    An optional ``sink`` callable is invoked on every append (e.g. to publish
    through the gateway). The sink must never block import or require a live
    connection at construction time.
    """

    def __init__(self, sink: Optional[Callable[[PlanningEvent], None]] = None) -> None:
        self._events: List[PlanningEvent] = []
        self._sink = sink

    def append(self, event: PlanningEvent) -> PlanningEvent:
        if not isinstance(event, PlanningEvent):
            raise TypeError("only PlanningEvent instances may be appended")
        self._events.append(event)
        if self._sink is not None:
            self._sink(event)
        return event

    def emit(
        self,
        event_type: EventType,
        subject_uuid: str,
        payload: Optional[Mapping[str, Any]] = None,
        gateway_context: str = "clss.gateway",
    ) -> PlanningEvent:
        """Convenience: construct + append in one call."""
        event = PlanningEvent(
            event_type=event_type,
            subject_uuid=subject_uuid,
            payload=dict(payload or {}),
            gateway_context=gateway_context,
        )
        return self.append(event)

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self):
        return iter(tuple(self._events))

    def all(self) -> Tuple[PlanningEvent, ...]:
        """Return an immutable snapshot of all events."""
        return tuple(self._events)

    def of_type(self, event_type: EventType) -> Tuple[PlanningEvent, ...]:
        return tuple(e for e in self._events if e.event_type == event_type)

    def for_subject(self, subject_uuid: str) -> Tuple[PlanningEvent, ...]:
        return tuple(e for e in self._events if e.subject_uuid == subject_uuid)

    def redact(self, event: PlanningEvent, payload: Mapping[str, Any]) -> PlanningEvent:
        """Produce a corrected *successor* event rather than mutating history.

        Append-only systems never rewrite the past. Corrections are expressed as
        new events; this helper returns the successor (the caller appends it).
        """
        successor = replace(
            event,
            payload=dict(payload),
            event_id=str(uuid.uuid4()),
            occurred_at=time.time(),
        )
        return successor
