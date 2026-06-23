"""The event SOURCE behind a clear interface — degrades to in-memory.

The engine derives state by replaying events. Those events live in the immutable
event store, reached THROUGH the gateway (INVARIANT: every cross-service call
passes the gateway). With ``clss.intelligence.dev.database_url`` /
``clss.intelligence.dev.gateway_url`` unset, there is no provider, so the engine
degrades to an in-memory event list — and because the projection paths are pure,
the result is identical either way.

This module names the interface and provides the in-memory implementation. A
real gateway-backed reader implements the same ``read_events`` shape; no
credentials are held here (INVARIANT 8: agents hold no credentials), and no
network call is made in the degraded path.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from .config import IntelligenceSettings, get_settings
from .models import EventEnvelope


class EventSource(ABC):
    """Read-only access to the immutable event log for replay. Read-ONLY — the
    engine never writes events; mastery is derived, never authored."""

    backend: str

    @abstractmethod
    def read_events(self, *, subject: UUID | None = None) -> list[EventEnvelope]:
        """Return the events to replay, optionally for one learner. Chronological
        order is not assumed — the engine sorts deterministically."""
        ...


class InMemoryEventSource(EventSource):
    """The degraded source: an explicit, append-only-in-spirit in-memory list.

    Clearly labelled as degraded. Useful for tests and local dev. Appending is
    allowed for fixture construction; the engine itself never mutates events.
    """

    backend = "in-memory (degraded — no clss.intelligence.dev.database_url)"

    def __init__(self, events: list[EventEnvelope] | None = None) -> None:
        self._events: list[EventEnvelope] = list(events or [])

    def append(self, event: EventEnvelope) -> None:
        self._events.append(event)

    def extend(self, events: list[EventEnvelope]) -> None:
        self._events.extend(events)

    def read_events(self, *, subject: UUID | None = None) -> list[EventEnvelope]:
        if subject is None:
            return list(self._events)
        return [e for e in self._events if e.canonical_uuid == subject]


def make_event_source(
    settings: IntelligenceSettings | None = None,
    *,
    events: list[EventEnvelope] | None = None,
) -> EventSource:
    """Construct the active event source. Returns the in-memory degraded source
    whenever no event provider is configured. A gateway-backed source would be
    selected here when ``database_url``/``gateway_url`` are present; until then
    the deterministic in-memory path is the supported path."""
    settings = settings or get_settings()
    if not settings.has_event_source:
        return InMemoryEventSource(events)
    # A gateway-backed reader would be returned here. It is intentionally not
    # implemented while no provider exists: the contract is the EventSource
    # interface, and the in-memory path keeps every deterministic test green.
    raise NotImplementedError(
        "Gateway-backed event source is not wired yet; set up the gateway reader "
        "behind the EventSource interface. Until then leave "
        "clss.intelligence.dev.database_url unset to use the in-memory source."
    )
