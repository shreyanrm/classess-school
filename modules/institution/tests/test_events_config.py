"""Event emission degrades gracefully; config reads env by name, never a value."""

from __future__ import annotations

import pytest

from app.config import (
    InstitutionSettings,
    get_settings,
    ENV_GATEWAY_URL,
    ENV_EVENT_SINK_URL,
)
from app.events import (
    EventEmitter,
    build_envelope,
    build_structure_payload,
    STRUCTURE_CHANGED,
)


def test_settings_default_degraded_and_names_vars():
    s = InstitutionSettings()
    assert s.has_gateway is False
    assert s.has_event_sink is False
    reasons = s.degraded_reasons()
    # Reports NAMES, never values.
    assert ENV_GATEWAY_URL in reasons
    assert ENV_EVENT_SINK_URL in reasons
    assert all(r.startswith("clss.institution.dev.") for r in reasons)


def test_get_settings_reads_env_by_name(monkeypatch):
    monkeypatch.setenv("CLSS_INSTITUTION_DEV_GATEWAY_URL", "https://gw.example")
    s = get_settings(refresh=True)
    assert s.gateway_url == "https://gw.example"
    assert s.has_gateway is True
    # Sink still missing -> still degraded (no direct egress without gateway+sink).
    assert s.has_event_sink is False
    monkeypatch.delenv("CLSS_INSTITUTION_DEV_GATEWAY_URL", raising=False)
    get_settings(refresh=True)


def test_emitter_degrades_to_returned_object():
    emitter = EventEmitter(InstitutionSettings())
    assert emitter.degraded is True
    result = emitter.emit_structure(
        canonical_uuid="00000000-0000-0000-0000-0000000000ff",
        consent_ref="11111111-1111-1111-1111-111111111111",
        institution_id="tenant-A",
        node_id="node-1",
        node_kind="school",
        action="created",
        label="Day School",
    )
    # Degraded: returned, NOT delivered over a wire.
    assert result.delivered is False
    assert "degraded" in result.sink
    assert result.envelope["type"] == STRUCTURE_CHANGED
    assert result.envelope["payload"]["institution_id"] == "tenant-A"
    # Append-only buffer holds it.
    assert len(emitter.buffered()) == 1


def test_emitter_with_sink_does_not_silently_send():
    # Even with both names set, the gateway POST is intentionally not wired:
    # it must raise rather than ever attempt direct/unauthenticated egress.
    s = InstitutionSettings(
        gateway_url="https://gw.example", event_sink_url="https://gw.example/events"
    )
    emitter = EventEmitter(s)
    assert emitter.degraded is False
    env = build_envelope(
        canonical_uuid="00000000-0000-0000-0000-0000000000ff",
        consent_ref="11111111-1111-1111-1111-111111111111",
        payload=build_structure_payload(
            institution_id="tenant-A", node_id="n1", node_kind="school",
            action="created",
        ),
        event_type=STRUCTURE_CHANGED,
    )
    with pytest.raises(NotImplementedError):
        emitter.emit(env)


def test_build_envelope_rejects_unknown_type():
    with pytest.raises(ValueError):
        build_envelope(
            canonical_uuid="u", consent_ref="c",
            payload={"institution_id": "t"}, event_type="not.a.type",
        )


def test_roster_payload_carries_opaque_member_only():
    emitter = EventEmitter(InstitutionSettings())
    result = emitter.emit_roster(
        canonical_uuid="00000000-0000-0000-0000-0000000000ff",
        consent_ref="11111111-1111-1111-1111-111111111111",
        institution_id="tenant-A",
        node_id="node-1",
        member_uuid="00000000-0000-0000-0000-000000000001",
        role="teacher",
        action="enrolled",
        valid_from="2026-04-01",
    )
    payload = result.envelope["payload"]
    assert payload["member_uuid"] == "00000000-0000-0000-0000-000000000001"
    # No PII fields in the roster payload.
    assert "name" not in payload and "email" not in payload and "phone" not in payload
