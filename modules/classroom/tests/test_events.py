"""Events: opaque-id enforcement, immutability, append-only, PII refusal."""

from __future__ import annotations

import pytest

from app import events
from app.events import Event, EventKind, EventLog, PIIRejected


def _uuid() -> str:
    return events.new_canonical_uuid()


def test_subject_must_be_opaque_uuid_not_pii():
    with pytest.raises(PIIRejected):
        Event(
            kind=EventKind.PRESENCE_JOINED,
            session_id="s1",
            subject_uuid="Asha Rao",  # a name, not an opaque uuid
        )


def test_payload_rejects_pii_keys():
    with pytest.raises(PIIRejected):
        Event(
            kind=EventKind.PRESENCE_JOINED,
            session_id="s1",
            subject_uuid=_uuid(),
            payload={"email": "x@y.z"},
        )


def test_event_is_immutable():
    e = Event(EventKind.PRESENCE_JOINED, "s1", _uuid())
    with pytest.raises(Exception):
        e.session_id = "s2"  # frozen dataclass


def test_log_is_append_only_and_snapshots():
    log = EventLog()
    a = Event(EventKind.SESSION_OPENED, "s1", _uuid())
    b = Event(EventKind.SESSION_CLOSED, "s1", _uuid())
    log.append(a)
    log.append(b)
    snap = log.events
    assert snap == (a, b)
    # mutating the snapshot tuple is impossible; appending more does not change it
    log.append(Event(EventKind.PRESENCE_LEFT, "s1", _uuid()))
    assert snap == (a, b)
    assert len(log) == 3


def test_envelope_is_gateway_intent_only():
    log = EventLog()
    log.append(Event(EventKind.SESSION_OPENED, "s1", _uuid()))
    env = log.envelope()
    d = env.to_dict()
    assert d["gateway_route"] == "events.append"
    assert len(d["events"]) == 1


def test_filtering_helpers():
    log = EventLog()
    u = _uuid()
    log.append(Event(EventKind.PRESENCE_JOINED, "s1", u))
    log.append(Event(EventKind.PRESENCE_LEFT, "s1", _uuid()))
    assert len(log.for_subject(u)) == 1
    assert len(log.by_kind(EventKind.PRESENCE_JOINED)) == 1
