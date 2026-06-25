"""The event SOURCE behind a clear interface — LIVE through the gateway, or
degrades to in-memory.

The engine derives state by replaying events. Those events live in the immutable
event store, reached THROUGH the gateway (INVARIANT 3: every cross-service call
passes the gateway). When ``clss.intelligence.dev.gateway_url`` /
``clss.intelligence.dev.database_url`` are set, :class:`GatewayEventSource` reads
the REAL event log over HTTPS via the gateway's generic route entrypoint
(``POST /v1/route/event-store/readEvents``), asserting the purpose (INVARIANT 6)
and presenting the bearer read from the environment by NAME (INVARIANT 8 — the
engine holds no credential of its own). With them unset there is no provider, so
the engine degrades to an in-memory event list — and because the projection
paths are pure, the result is identical either way.

The HTTP transport is INJECTABLE so the module imports with no network and tests
run fully OFFLINE. A transport / parse error fails SAFE: the gateway source
returns no events rather than crashing the read (the view then shows not-started,
observably degraded, never a fabricated mastery).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol
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


# ---------------------------------------------------------------------------
# The HTTP transport seam (real httpx by default; injectable for offline tests)
# ---------------------------------------------------------------------------

class HttpTransport(Protocol):
    """The HTTP seam the gateway reader posts through. Injected in tests for
    offline operation. Returns the parsed JSON body (a list of event envelopes);
    raises on transport / non-2xx so the reader can fail SAFE."""

    def post_json(
        self, *, url: str, headers: dict[str, str], params: dict[str, Any], timeout: float
    ) -> Any:
        ...


@dataclass
class HttpxTransport:
    """A real httpx-backed transport. Imported lazily to stay import-safe."""

    def post_json(
        self, *, url: str, headers: dict[str, str], params: dict[str, Any], timeout: float
    ) -> Any:
        import httpx  # local import: module stays import-safe / tests stay offline

        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, params=params, json={})
            resp.raise_for_status()
            return resp.json()


# The gateway's generic route entrypoint + the event-store read operation. These
# are public route templates, not secrets.
GATEWAY_ROUTE_PATH = "/v1/route/event-store/readEvents"
# The purpose asserted for this cross-context read (INVARIANT 6). The engine
# replays the full mastery history, so it reads under the "mastery" purpose.
READ_PURPOSE = "mastery"


@dataclass
class GatewayEventSource(EventSource):
    """The LIVE source: reads the immutable event log THROUGH the gateway.

    Every read passes the gateway (INVARIANT 3) at the generic route entrypoint,
    asserting the purpose (INVARIANT 6) via ``X-Consent-Purpose`` and presenting
    the bearer read by NAME from settings (INVARIANT 8 — never hardcoded, never
    logged). The events come back as a JSON array of envelopes, validated against
    the same :class:`EventEnvelope` the engine replays.

    Fails SAFE: a missing token, a transport error, or an unparseable body yields
    an EMPTY event list (the engine then derives not-started, observably degraded)
    rather than crashing — it NEVER fabricates events.
    """

    settings: IntelligenceSettings
    transport: HttpTransport = field(default_factory=HttpxTransport)
    timeout_seconds: float = 20.0

    backend = "gateway (live — clss.intelligence.dev.gateway_url)"

    def _raw_token(self) -> str | None:
        token = self.settings.gateway_token
        if token is None or not str(token).strip():
            return None
        return str(token)

    def read_events(self, *, subject: UUID | None = None) -> list[EventEnvelope]:
        token = self._raw_token()
        gateway_url = self.settings.gateway_url
        if token is None or not gateway_url:
            # No credential / no egress => fail safe with no events (degraded,
            # observable), never a fabricated history.
            return []
        url = gateway_url.rstrip("/") + GATEWAY_ROUTE_PATH
        # The bearer rides ONLY in the Authorization header, at call time.
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Consent-Purpose": READ_PURPOSE,
            "Content-Type": "application/json",
        }
        params: dict[str, Any] = {"purpose": READ_PURPOSE}
        if subject is not None:
            params["canonical_uuid"] = str(subject)
        try:
            data = self.transport.post_json(
                url=url, headers=headers, params=params, timeout=self.timeout_seconds
            )
        except Exception:
            return []  # fail safe — never crash the read, never fabricate.
        return self._parse(data)

    @staticmethod
    def _parse(data: Any) -> list[EventEnvelope]:
        """Validate a gateway response into event envelopes; malformed => [].

        Accepts either a bare JSON array (the event-store read shape) or an
        envelope ``{"events": [...]}``. Any row that does not validate is dropped
        (fail safe) rather than aborting the whole replay."""
        rows: Any
        if isinstance(data, dict):
            rows = data.get("events", [])
        else:
            rows = data
        if not isinstance(rows, list):
            return []
        out: list[EventEnvelope] = []
        for row in rows:
            try:
                out.append(EventEnvelope.model_validate(row))
            except Exception:
                continue
        return out


def make_event_source(
    settings: IntelligenceSettings | None = None,
    *,
    events: list[EventEnvelope] | None = None,
    transport: HttpTransport | None = None,
) -> EventSource:
    """Construct the active event source.

    Returns the LIVE :class:`GatewayEventSource` when the event provider is
    configured (``clss.intelligence.dev.database_url`` +
    ``clss.intelligence.dev.gateway_url``); otherwise the in-memory degraded
    source so the deterministic path stays green offline. ``transport`` is
    injectable for offline tests of the live path."""
    settings = settings or get_settings()
    if not settings.has_event_source:
        return InMemoryEventSource(events)
    if transport is not None:
        return GatewayEventSource(settings=settings, transport=transport)
    return GatewayEventSource(settings=settings)
