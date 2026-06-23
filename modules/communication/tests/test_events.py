"""Event emission: append-only, opaque-only (never the message body),
screened-message-only, degrades offline."""

from __future__ import annotations

import pytest

from app.config import CommunicationSettings
from app.events import (
    EventEmitter,
    build_meeting_scheduled_payload,
    build_message_sent_payload,
    build_safeguarding_escalated_payload,
    build_sentiment_observed_payload,
)


CANON = "9999aaaa-0000-4000-8000-000000000001"
CONSENT = "cccccccc-0000-4000-8000-000000000003"
SENDER = "9999aaaa-0000-4000-8000-00000000000c"


def test_emitter_degrades_to_in_memory_sink_with_no_gateway():
    emitter = EventEmitter(CommunicationSettings())
    assert emitter.degraded is True
    assert "in-memory" in emitter.sink_label
    assert "clss.communication.dev.gateway_url" in emitter.sink_label


def test_message_sent_carries_the_safety_verdict_not_the_body():
    payload = build_message_sent_payload(
        surface="hub", context_ref="ctx-a", sender_ref=SENDER,
        safety_severity="none", flagged=False,
    )
    assert payload["screened"] is True
    assert "body" not in payload and "text" not in payload and "message" not in payload
    assert payload["safety_severity"] == "none"


def test_message_sent_refuses_an_unscreened_message():
    # No unmonitored channel: an event for an unscreened message is a defect.
    with pytest.raises(ValueError):
        build_message_sent_payload(
            surface="hub", context_ref="ctx-a", sender_ref=SENDER,
            safety_severity="none", flagged=False, screened=False,
        )


def test_payload_builders_reject_pii_and_body_keys():
    # The guard catches any attempt to smuggle a body/PII key (defense in depth).
    for builder in (
        lambda: build_sentiment_observed_payload(
            surface="companion", context_ref="ctx-a", band="needs_attention",
            evidence="repeated short replies",
        ),
    ):
        payload = builder()
        forbidden = {"name", "email", "phone", "body", "text", "message"}
        assert not (forbidden & set(payload.keys()))


def test_safeguarding_escalated_records_a_human_was_routed_in():
    payload = build_safeguarding_escalated_payload(
        surface="companion", writer_ref=CANON, severity="crisis",
        categories=["self_harm"], owner_role="safeguarding_lead", is_crisis=True,
    )
    assert payload["routed_to_human"] is True
    assert payload["is_crisis"] is True
    assert payload["owner_role"] == "safeguarding_lead"


def test_message_sent_round_trips_through_the_envelope():
    emitter = EventEmitter(CommunicationSettings())
    result = emitter.emit_message_sent(
        canonical_uuid=CANON, consent_ref=CONSENT, surface="hub",
        context_ref="ctx-a", sender_ref=SENDER, safety_severity="none", flagged=False,
    )
    assert result.delivered is False  # local-only in the degraded path.
    env = result.envelope
    assert env["type"] == "message.sent"
    assert env["purpose"] == "communication"
    assert env["canonical_uuid"] == CANON
    assert env["schema_version"] == "v1"
    assert emitter.buffered() == [env]


def test_safeguarding_escalation_uses_intervention_purpose():
    emitter = EventEmitter(CommunicationSettings())
    result = emitter.emit_safeguarding_escalated(
        canonical_uuid=CANON, consent_ref=CONSENT, surface="companion",
        writer_ref=CANON, severity="crisis", categories=["self_harm"],
        owner_role="safeguarding_lead", is_crisis=True,
    )
    assert result.envelope["purpose"] == "intervention"
    assert result.envelope["type"] == "safeguarding.escalated"


def test_meeting_scheduled_is_partnership_shaped_and_opaque():
    payload = build_meeting_scheduled_payload(
        meeting_id="m-1", context_ref="ctx-a",
        participant_refs=[CANON, SENDER], purpose_label="parent_teacher_partnership",
        scheduled_for="2026-07-01T10:00:00+00:00",
    )
    assert payload["purpose_label"] == "parent_teacher_partnership"
    assert payload["participant_refs"] == [CANON, SENDER]


def test_appends_are_immutable_across_multiple_emits():
    emitter = EventEmitter(CommunicationSettings())
    emitter.emit_message_sent(
        canonical_uuid=CANON, consent_ref=CONSENT, surface="hub",
        context_ref="ctx-a", sender_ref=SENDER, safety_severity="none", flagged=False,
    )
    first_snapshot = emitter.buffered()
    emitter.emit_sentiment_observed(
        canonical_uuid=CANON, consent_ref=CONSENT, surface="companion",
        context_ref="ctx-a", band="positive", evidence="completed the step independently",
    )
    assert len(first_snapshot) == 1
    assert len(emitter.buffered()) == 2
