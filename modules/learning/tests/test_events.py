"""Evidence event emission — coherent attempts, PII-free, append-only, degraded."""

from __future__ import annotations

import pytest

from learning import events
from learning.events import EventEmitter, build_attempt_payload, build_envelope

from .conftest import CONSENT, LEARNER_A, T_EUCLID


def test_attempt_mode_derived_from_assistance_level():
    # The keystone flag is never guessed away from the rung used.
    indep = build_attempt_payload(topic_id=T_EUCLID, assistance_level="Independent", correct=True, difficulty=0.5, time_taken_ms=30_000)
    assert indep["mode"] == "independent"
    supp = build_attempt_payload(topic_id=T_EUCLID, assistance_level="Hint", correct=True, difficulty=0.5, time_taken_ms=30_000)
    assert supp["mode"] == "supported"


def test_incoherent_attempt_is_rejected():
    # mode 'independent' with a help rung must be refused (the contract's rule).
    with pytest.raises(ValueError):
        build_attempt_payload(
            topic_id=T_EUCLID, assistance_level="Coach", correct=True,
            difficulty=0.5, time_taken_ms=30_000, mode="independent",
        )
    with pytest.raises(ValueError):
        build_attempt_payload(
            topic_id=T_EUCLID, assistance_level="Independent", correct=True,
            difficulty=0.5, time_taken_ms=30_000, mode="supported",
        )


def test_practice_attempt_has_no_completion_tick():
    payload = events.build_mastery_evidence_attempt(
        topic_id=T_EUCLID, assistance_level="Hint", correct=True, difficulty=0.6, time_taken_ms=40_000, score=0.7
    )
    # It is an attempt event, not a "completed" flag.
    assert "completed" not in payload and "done" not in payload
    assert payload["assistance_level"] == "Hint"


def test_envelope_is_pii_free_and_attributed():
    payload = build_attempt_payload(topic_id=T_EUCLID, assistance_level="Hint", correct=True, difficulty=0.5, time_taken_ms=30_000)
    env = build_envelope(canonical_uuid=LEARNER_A, consent_ref=CONSENT, payload=payload, purpose="mastery")
    # Attribution present, opaque only — no name/email field anywhere.
    assert env["canonical_uuid"] == LEARNER_A
    assert env["consent_ref"] == CONSENT
    assert env["purpose"] == "mastery"
    assert env["type"] == "attempt.recorded"
    blob = str(env).lower()
    assert "email" not in blob and "name" not in blob


def test_emitter_degrades_to_in_memory_append_only_sink():
    em = EventEmitter()
    assert em.degraded  # no gateway/sink configured in tests
    r1 = em.emit_attempt(
        canonical_uuid=LEARNER_A, consent_ref=CONSENT, topic_id=T_EUCLID,
        assistance_level="Hint", correct=True, difficulty=0.5, time_taken_ms=30_000, score=0.8,
    )
    assert r1.delivered is False  # local only, the caller knows it is degraded
    assert "degraded" in r1.sink
    r2 = em.emit_attempt(
        canonical_uuid=LEARNER_A, consent_ref=CONSENT, topic_id=T_EUCLID,
        assistance_level="Independent", correct=True, difficulty=0.6, time_taken_ms=20_000,
    )
    # Append-only: both events are buffered, never overwritten.
    assert len(em.buffered()) == 2
    assert em.buffered()[1]["payload"]["mode"] == "independent"


def test_difficulty_required_and_bounded():
    with pytest.raises(ValueError):
        build_attempt_payload(topic_id=T_EUCLID, assistance_level="Hint", correct=True, difficulty=1.5, time_taken_ms=10)
