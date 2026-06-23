"""Portfolio/credential events: PII-free, attributed, append-only, degraded."""

from __future__ import annotations

import pytest

from app import events
from app.events import EventEmitter, build_credential_issued_payload, build_envelope

from .conftest import CONSENT, EVENT_1, EVENT_2, LEARNER_A, T_GEOMETRY


def test_artifact_added_requires_provenance():
    with pytest.raises(ValueError):
        events.build_artifact_added_payload(
            artifact_id="art-1",
            topic_id=T_GEOMETRY,
            source_event_ids=[],
            produced_mode="independent",
            content_ref="ref://x",
            title="Model",
        )


def test_credential_statement_rejects_a_number():
    with pytest.raises(ValueError):
        build_credential_issued_payload(
            credential_id="cred-1",
            topic_id=T_GEOMETRY,
            claim_kind="independent-mastery",
            statement="scored 99",
            source_event_ids=[EVENT_1],
            verifiable=True,
        )


def test_envelope_is_pii_free_and_attributed():
    payload = build_credential_issued_payload(
        credential_id="cred-1",
        topic_id=T_GEOMETRY,
        claim_kind="independent-mastery",
        statement="demonstrated independently",
        source_event_ids=[EVENT_1, EVENT_2],
        verifiable=True,
    )
    env = build_envelope(
        canonical_uuid=LEARNER_A,
        consent_ref=CONSENT,
        payload=payload,
        event_type="credential.issued",
    )
    assert env["canonical_uuid"] == LEARNER_A
    assert env["consent_ref"] == CONSENT
    assert env["purpose"] == "mastery"
    assert env["type"] == "credential.issued"
    blob = str(env).lower()
    assert "email" not in blob and "phone" not in blob


def test_pii_key_in_payload_is_rejected():
    with pytest.raises(ValueError):
        build_envelope(
            canonical_uuid=LEARNER_A,
            consent_ref=CONSENT,
            payload={"artifact_id": "a", "student_name": "leak"},
            event_type="portfolio.artifact_added",
        )


def test_emitter_degrades_to_in_memory_append_only_sink():
    em = EventEmitter()
    assert em.degraded
    r1 = em.emit_artifact_added(
        canonical_uuid=LEARNER_A,
        consent_ref=CONSENT,
        artifact_id="art-1",
        topic_id=T_GEOMETRY,
        source_event_ids=[EVENT_1],
        produced_mode="independent",
        content_ref="ref://1",
        title="Model",
    )
    assert r1.delivered is False
    assert "degraded" in r1.sink
    r2 = em.emit_credential_issued(
        canonical_uuid=LEARNER_A,
        consent_ref=CONSENT,
        credential_id="cred-1",
        topic_id=T_GEOMETRY,
        claim_kind="independent-mastery",
        statement="demonstrated independently",
        source_event_ids=[EVENT_1],
        verifiable=False,
    )
    # Append-only: both events buffered, never overwritten.
    assert len(em.buffered()) == 2
    assert em.buffered()[0]["type"] == "portfolio.artifact_added"
    assert em.buffered()[1]["type"] == "credential.issued"


def test_event_purpose_is_mastery_for_the_learner_record():
    payload = events.build_artifact_featured_payload(artifact_id="art-1", featured=True)
    env = build_envelope(
        canonical_uuid=LEARNER_A,
        consent_ref=CONSENT,
        payload=payload,
        event_type="portfolio.artifact_featured",
    )
    assert env["purpose"] == "mastery"
