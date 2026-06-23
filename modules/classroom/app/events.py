"""Delivery / engagement / grasp events for the classroom (d7).

Events are the only durable record this engine emits. They are immutable and
append-only: once constructed an event cannot be mutated, and the log only
grows. Every event carries an opaque ``canonical_uuid`` for the subject and
never carries PII.

Persisting events is a consequential, gateway-routed effect. This module does
not write anywhere; it produces ``EventEnvelope`` intents that a caller hands to
the gateway. Degrading gracefully with no live keys / DB simply means the log
stays in memory and nothing is flushed.
"""

from __future__ import annotations

import enum
import re
import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping

# ---------------------------------------------------------------------------
# Constants / env contract
# ---------------------------------------------------------------------------

#: Env var (server-side only) holding the gateway base URL the caller flushes to.
ENV_GATEWAY_URL = "clss.classroom.prod.gateway_url"
#: Env var (server-side only) holding the event-sink credential handle.
ENV_EVENT_SINK_TOKEN = "clss.classroom.prod.event_sink_token"

#: Opaque-id shape: the canonical_uuid must look like a UUID and never a name.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

# Keys that must never appear in an event payload (defense in depth against PII).
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "name",
        "full_name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "address",
        "face",
        "face_image",
        "image",
        "photo",
        "raw_image",
        "dob",
        "date_of_birth",
        "ssn",
        "aadhaar",
    }
)


class EventKind(str, enum.Enum):
    """Categories of classroom event. Append new kinds; never repurpose."""

    # delivery lifecycle
    SESSION_OPENED = "delivery.session_opened"
    SESSION_CLOSED = "delivery.session_closed"
    PRESENCE_JOINED = "delivery.presence_joined"
    PRESENCE_LEFT = "delivery.presence_left"
    BREAKOUT_OPENED = "delivery.breakout_opened"
    BREAKOUT_CLOSED = "delivery.breakout_closed"
    BOARD_PAGE_ADDED = "delivery.board_page_added"
    BOARD_OBJECT_COMMITTED = "delivery.board_object_committed"
    BOARD_THEME_CHANGED = "delivery.board_theme_changed"
    BOARD_FRAME_FROZEN = "delivery.board_frame_frozen"
    BOARD_FRAME_RESUMED = "delivery.board_frame_resumed"
    BOARD_DOCUMENT_SHARED = "delivery.board_document_shared"
    BOARD_CONTENT_VERIFIED = "delivery.board_content_verified"
    BOARD_CONTENT_INTERACTED = "delivery.board_content_interacted"
    PERIOD_LAUNCHED = "delivery.period_launched"

    # engagement (assistive, non-punitive, non-identity-graded)
    ENGAGEMENT_SIGNAL = "engagement.signal"
    POLL_OPENED = "engagement.poll_opened"
    POLL_RESPONSE = "engagement.poll_response"
    POLL_CLOSED = "engagement.poll_closed"
    DEVICE_FREE_CHECK = "engagement.device_free_check"
    ROOM_PHOTO_CAPTURE = "engagement.room_photo_capture"
    RAISED_HAND = "engagement.raised_hand"
    NO_PERSON_PRESENT = "engagement.no_person_present"
    ENGAGEMENT_PERFORMANCE_LINK = "engagement.performance_link"

    # grasp (learning evidence, never a verdict on a person)
    GRASP_OBSERVED = "grasp.observed"


def is_opaque_uuid(value: str) -> bool:
    """Return True only for a lowercase canonical UUID string."""
    return bool(isinstance(value, str) and _UUID_RE.match(value))


def new_canonical_uuid() -> str:
    """Mint a fresh opaque canonical_uuid (for tests / synthetic subjects)."""
    return str(uuid.uuid4())


class PIIRejected(ValueError):
    """Raised when an event payload would carry PII."""


def _assert_pii_free(payload: Mapping[str, Any]) -> None:
    for key in payload:
        if str(key).lower() in _FORBIDDEN_PAYLOAD_KEYS:
            raise PIIRejected(
                f"payload key {key!r} is forbidden: events carry no PII"
            )


@dataclass(frozen=True)
class Event:
    """An immutable, append-only classroom event.

    ``subject_uuid`` is the opaque canonical_uuid of the learner/teacher the
    event concerns. ``payload`` is screened to be PII-free at construction.
    """

    kind: EventKind
    session_id: str
    subject_uuid: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EventKind):
            raise TypeError("kind must be an EventKind")
        if not self.session_id:
            raise ValueError("session_id is required")
        if not is_opaque_uuid(self.subject_uuid):
            raise PIIRejected(
                "subject_uuid must be an opaque canonical_uuid, never PII"
            )
        _assert_pii_free(self.payload)
        # Freeze the payload into an immutable mapping copy.
        object.__setattr__(self, "payload", dict(self.payload))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind.value,
            "session_id": self.session_id,
            "subject_uuid": self.subject_uuid,
            "occurred_at": self.occurred_at,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class EventEnvelope:
    """A gateway-bound intent wrapping one or more events to flush.

    Building an envelope does NOT send anything. The caller must pass it to the
    gateway; that is the single egress path for durable writes.
    """

    events: tuple[Event, ...]
    gateway_route: str = "events.append"

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_route": self.gateway_route,
            "events": [e.to_dict() for e in self.events],
        }


class EventLog:
    """In-memory, append-only event log.

    Safe with no DB: it simply accumulates events. Flushing produces a
    gateway envelope (an intent) rather than performing I/O here.
    """

    def __init__(self) -> None:
        self._events: list[Event] = []

    def __len__(self) -> int:
        return len(self._events)

    def append(self, event: Event) -> Event:
        """Append an event. The log never mutates or deletes prior entries."""
        if not isinstance(event, Event):
            raise TypeError("can only append Event instances")
        self._events.append(event)
        return event

    def extend(self, events: Iterable[Event]) -> None:
        for event in events:
            self.append(event)

    @property
    def events(self) -> tuple[Event, ...]:
        """A snapshot tuple; callers cannot mutate the underlying log."""
        return tuple(self._events)

    def by_kind(self, kind: EventKind) -> tuple[Event, ...]:
        return tuple(e for e in self._events if e.kind == kind)

    def for_subject(self, subject_uuid: str) -> tuple[Event, ...]:
        return tuple(e for e in self._events if e.subject_uuid == subject_uuid)

    def envelope(self, gateway_route: str = "events.append") -> EventEnvelope:
        """Wrap the current log as a gateway-bound flush intent."""
        return EventEnvelope(events=self.events, gateway_route=gateway_route)


def redact(event: Event, **overrides: Any) -> Event:
    """Return a copy of an event with overridden fields, re-screened for PII.

    Used to build a derived projection (e.g. a cross-context view) without
    mutating the original immutable event.
    """
    return replace(event, **overrides)
