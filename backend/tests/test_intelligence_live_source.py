"""The governed intelligence READ uses the REAL persisted event store when a
source is configured, and degrades to the PII-free seed — OBSERVABLY — when not.

This is the fix for the fixture-backed read: ``intelligence_views.read`` used to
replay a hardcoded ``_seed_events()`` UNCONDITIONALLY, so mastery / gaps /
recommendations / class-insights were synthetic — divorced from the events the
web surface persists to ``platform.events``. It now builds the REAL event source
through the engine's ``spine/intelligence/app/source.py`` seam
(``make_event_source`` -> ``GatewayEventSource`` when the DB pooler is
configured) and feeds those PERSISTED events into the ONE engine.

Proven here, fully OFFLINE (the event source is MOCKED — no real DB, no paid
call, no network):

  LIVE WHEN CONFIGURED
    With a configured source, ``read`` replays the events the source returns —
    NOT the seed — and marks the body OBSERVABLY ``source: "live"`` so it can
    never be mistaken for the degraded seed. A live-only learner (absent from the
    seed) gets a real, derived mastery band, which is only possible if the live
    events actually reached the engine.

  SEED-DEGRADE WHEN NOT
    With no source configured, ``read`` replays the seed and marks the body
    OBSERVABLY ``source: "seed", degraded: true`` (never silently pretending to
    be live), and names the env vars that would lift the degrade.

  CONFIGURED-BUT-EMPTY DEGRADES OBSERVABLY
    A configured source that returns nothing (no token / unreachable gateway /
    empty log) degrades to the seed and is marked degraded — never an empty,
    fabricated-looking live view.

CONFIDENTIALITY: every id is an opaque canonical ref. No PII, no names.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from backend import intelligence_views

pytestmark = pytest.mark.skipif(
    not intelligence_views.available(), reason="intelligence engine not installed"
)

_TOPIC = "70000000-0000-4000-8000-000000000001"
# A learner the seed does NOT contain — a real mastery for them can only come
# from LIVE events reaching the engine, never from the seed.
_LIVE_ONLY = "c0000000-0000-4000-8000-00000000000c"


def _live_event(subject: str, score: float, when: datetime):
    """A real persisted-shape attempt envelope the engine replays (the same shape
    the web's /api/events route persists to platform.events)."""
    engine = intelligence_views._engine
    return engine.EventEnvelope(
        event_id=uuid.uuid4(),
        occurred_at=when,
        recorded_at=when,
        app="learner",
        canonical_uuid=uuid.UUID(subject),
        purpose="assessment",
        consent_ref=uuid.uuid4(),
        type="attempt.recorded",
        payload={
            "attempt_id": str(uuid.uuid4()),
            "ontology": {"topic_id": _TOPIC},
            "mode": "independent",
            "assistance_level": "Independent",
            "correct": True,
            "score": score,
            "time_taken_ms": 22_000,
            "difficulty": 0.6,
        },
    )


class _FakeLiveSource:
    """A mock of the engine's EventSource that returns PERSISTED events without a
    DB or network — proves the live read path is TAKEN, fully offline."""

    backend = "gateway (live — MOCK)"

    def __init__(self, events):
        self._events = events

    def read_events(self, *, subject=None):
        if subject is None:
            return list(self._events)
        return [e for e in self._events if e.canonical_uuid == subject]


# --------------------------------------------------------------------------- #
# LIVE WHEN CONFIGURED — the real persisted events drive the projection.
# --------------------------------------------------------------------------- #
def test_mastery_uses_live_events_when_source_configured(monkeypatch):
    when = datetime(2026, 1, 14, 12, 0, 0, tzinfo=timezone.utc)
    live = [_live_event(_LIVE_ONLY, 0.9, when), _live_event(_LIVE_ONLY, 0.88, when)]
    _patch_live(monkeypatch, live)

    body = intelligence_views.read(view=f"mastery:{_TOPIC}", subject_uuid=_LIVE_ONLY)

    # Observably LIVE — never mistaken for the seed.
    assert body["_meta"]["source"] == "live"
    assert body["_meta"]["degraded"] is False
    # A live-only learner has a derived reading -> the LIVE events reached the
    # engine (the seed never contains this learner).
    assert body["reading"]["band"] in (
        "not-started", "emerging", "developing", "secure", "independent"
    )
    assert body["observation_count"] == 2  # exactly the two live attempts
    assert intelligence_views.last_source_meta()["source"] == "live"


def test_class_insights_live_meta_when_configured(monkeypatch):
    when = datetime(2026, 1, 14, 12, 0, 0, tzinfo=timezone.utc)
    _patch_live(monkeypatch, [_live_event(_LIVE_ONLY, 0.9, when)])

    body = intelligence_views.read(view="class-insights", subject_uuid="inst-1")
    assert body["_meta"]["source"] == "live"
    assert "summary" in body and "reads" in body


# --------------------------------------------------------------------------- #
# SEED-DEGRADE WHEN NOT CONFIGURED — observably marked, never silently faked.
# --------------------------------------------------------------------------- #
def test_mastery_degrades_to_seed_when_unconfigured(monkeypatch):
    # Default settings: nothing configured (and no shared CLSS_DATABASE_URL).
    monkeypatch.delenv("CLSS_DATABASE_URL", raising=False)
    monkeypatch.setattr(
        intelligence_views, "_build_settings",
        lambda: intelligence_views._engine.get_settings(),
    )
    seed_a = "a0000000-0000-4000-8000-00000000000a"  # a learner the seed contains
    body = intelligence_views.read(view=f"mastery:{_TOPIC}", subject_uuid=seed_a)

    assert body["_meta"]["source"] == "seed"
    assert body["_meta"]["degraded"] is True
    # Names (not values) of the env vars that would lift the degrade.
    assert "clss.intelligence.dev.database_url" in body["_meta"]["degraded_reasons"]
    # The seed learner still derives a band (the deterministic fallback works).
    assert body["reading"]["band"] in (
        "not-started", "emerging", "developing", "secure", "independent"
    )


def test_recommendations_list_observable_via_header_meta(monkeypatch):
    # Gaps / recommendations are bare lists; the inline marker can't ride them,
    # so last_source_meta (which the HTTP faucet surfaces on a header) carries it.
    monkeypatch.delenv("CLSS_DATABASE_URL", raising=False)
    monkeypatch.setattr(
        intelligence_views, "_build_settings",
        lambda: intelligence_views._engine.get_settings(),
    )
    recs = intelligence_views.read(view="recommendations", subject_uuid=None)
    assert isinstance(recs, list)  # contract shape preserved (no inline marker)
    assert intelligence_views.last_source_meta()["degraded"] is True


# --------------------------------------------------------------------------- #
# CONFIGURED-BUT-EMPTY — degrade OBSERVABLY to the seed, never an empty live view.
# --------------------------------------------------------------------------- #
def test_configured_but_empty_source_degrades_to_seed(monkeypatch):
    _patch_live(monkeypatch, [])  # configured, but the source returns nothing
    seed_a = "a0000000-0000-4000-8000-00000000000a"
    body = intelligence_views.read(view=f"mastery:{_TOPIC}", subject_uuid=seed_a)

    # Marked degraded -> never mistaken for a (fabricated-looking) empty live view.
    assert body["_meta"]["source"] == "seed"
    assert body["_meta"]["degraded"] is True
    # But the seed still answers (the deterministic fallback), so the learner has
    # a real band rather than an empty body.
    assert body["reading"]["band"] in (
        "not-started", "emerging", "developing", "secure", "independent"
    )


# --------------------------------------------------------------------------- #
# helper: patch the engine boundary to a configured source serving `events`.
# --------------------------------------------------------------------------- #
def _patch_live(monkeypatch, events):
    settings = intelligence_views._engine.get_settings().model_copy(
        update={
            "database_url": "postgres://events-MOCK",  # PRESENCE => live source
            "gateway_url": "https://gateway.MOCK",
            "gateway_token": "bearer-MOCK",
        }
    )
    monkeypatch.setattr(intelligence_views, "_build_settings", lambda: settings)
    # The real make_event_source IGNORES the in-memory ``events`` seed on the live
    # path (it only feeds the degraded InMemoryEventSource); the live gateway
    # source reads the persisted log. The fake mirrors that: it serves the
    # configured ``events`` (captured here) and ignores the factory's seed kwarg.
    source = _FakeLiveSource(events)
    monkeypatch.setattr(
        intelligence_views._engine,
        "make_event_source",
        lambda s, events=None: source,
        raising=True,
    )
