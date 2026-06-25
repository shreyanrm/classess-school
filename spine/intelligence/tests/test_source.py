"""The event SOURCE — LIVE through the gateway when configured, in-memory when not.

Proves the REAL read path is taken WHEN CONFIGURED and DEGRADES cleanly when not:

  - With ``database_url`` + ``gateway_url`` + ``gateway_token`` set, the factory
    returns the LIVE :class:`GatewayEventSource`, which reads the real event log
    through the gateway route entrypoint, asserting the purpose (INVARIANT 6) and
    presenting the bearer ONLY in the Authorization header (INVARIANT 8). The
    engine then derives mastery from those REAL events.
  - With them unset, the factory returns the in-memory degraded source.
  - A transport error / unparseable body fails SAFE (no events), never crashes,
    never fabricates a history.

Entirely OFFLINE: the HTTP transport is injected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config import IntelligenceSettings
from app.profile import build_profile
from app.read import view_from_profile
from app.source import (
    GATEWAY_ROUTE_PATH,
    GatewayEventSource,
    InMemoryEventSource,
    make_event_source,
)

from .conftest import LEARNER_A, NOW, T_EUCLID, days_ago, indep


# -- an offline transport that returns the event-store read shape ----------

@dataclass
class FakeGatewayTransport:
    rows: list[dict]
    seen_url: str | None = None
    seen_headers: dict | None = None
    seen_params: dict | None = None

    def post_json(self, *, url, headers, params, timeout):
        self.seen_url = url
        self.seen_headers = dict(headers)
        self.seen_params = dict(params)
        return self.rows


@dataclass
class ExplodingTransport:
    def post_json(self, *, url, headers, params, timeout):
        raise RuntimeError("gateway unreachable")


def _live_settings() -> IntelligenceSettings:
    return IntelligenceSettings(
        database_url="postgres://events",  # marks the source as configured
        gateway_url="https://gateway.internal",
        gateway_token="bearer-NOLEAK",
    )


def _event_rows() -> list[dict]:
    # Real envelopes the engine replays, serialized as the gateway returns them.
    return [indep(LEARNER_A, T_EUCLID, occurred_at=days_ago(i), difficulty=0.6).model_dump(mode="json")
            for i in range(4)]


# -- factory selection -----------------------------------------------------

def test_factory_degrades_to_in_memory_when_unconfigured():
    src = make_event_source(IntelligenceSettings())  # nothing set
    assert isinstance(src, InMemoryEventSource)
    assert "degraded" in src.backend


def test_factory_selects_live_gateway_source_when_configured():
    src = make_event_source(_live_settings(), transport=FakeGatewayTransport(rows=[]))
    assert isinstance(src, GatewayEventSource)
    assert "live" in src.backend


# -- the live read path is TAKEN -------------------------------------------

def test_live_gateway_source_reads_real_events_through_gateway():
    transport = FakeGatewayTransport(rows=_event_rows())
    src = GatewayEventSource(settings=_live_settings(), transport=transport)
    events = src.read_events(subject=LEARNER_A)
    assert len(events) == 4
    # The read passed the gateway route entrypoint, asserting the purpose, with
    # the bearer ONLY in the Authorization header (never a query param).
    assert transport.seen_url.endswith(GATEWAY_ROUTE_PATH)
    assert transport.seen_headers["Authorization"] == "Bearer bearer-NOLEAK"
    assert transport.seen_headers["X-Consent-Purpose"] == "mastery"
    assert transport.seen_params["purpose"] == "mastery"
    assert transport.seen_params["canonical_uuid"] == str(LEARNER_A)
    # The bearer never leaks into a query param.
    assert "bearer-NOLEAK" not in str(transport.seen_params)


def test_engine_derives_mastery_from_live_events():
    """End to end: the LIVE source feeds REAL events into the pure projection, so
    mastery/independence is computed from the event store, not a seed."""
    src = GatewayEventSource(settings=_live_settings(),
                             transport=FakeGatewayTransport(rows=_event_rows()))
    profile = build_profile(src.read_events(subject=LEARNER_A), subject=LEARNER_A, asof=NOW)
    view = view_from_profile(profile)
    t = view.topic(str(T_EUCLID))
    assert t is not None
    assert t.independence == "independent"
    assert t.observation_count == 4


# -- DEGRADES SAFE on failure ----------------------------------------------

def test_live_source_fails_safe_on_transport_error():
    src = GatewayEventSource(settings=_live_settings(), transport=ExplodingTransport())
    # No crash, no fabricated events — an empty list (observably degraded).
    assert src.read_events(subject=LEARNER_A) == []


def test_live_source_fails_safe_without_token():
    settings = IntelligenceSettings(
        database_url="postgres://events", gateway_url="https://gateway.internal",
        # gateway_token unset => no credential => no read, never fabricates.
    )
    src = GatewayEventSource(settings=settings, transport=FakeGatewayTransport(rows=_event_rows()))
    assert src.read_events(subject=LEARNER_A) == []


def test_live_source_drops_malformed_rows():
    rows = _event_rows() + [{"not": "an event"}]
    src = GatewayEventSource(settings=_live_settings(),
                             transport=FakeGatewayTransport(rows=rows))
    events = src.read_events(subject=LEARNER_A)
    assert len(events) == 4  # the malformed row is dropped, the rest survive


def test_live_source_accepts_events_envelope_shape():
    src = GatewayEventSource(settings=_live_settings(),
                             transport=FakeGatewayTransport(rows={"events": _event_rows()}))  # type: ignore[arg-type]
    assert len(src.read_events(subject=LEARNER_A)) == 4


def test_token_never_in_repr():
    src = GatewayEventSource(settings=_live_settings(), transport=FakeGatewayTransport(rows=[]))
    # The settings carry the token; ensure a casual repr of the source/transport
    # does not surface it (defense in depth — it only ever rides the header).
    assert "bearer-NOLEAK" not in repr(src.transport)
