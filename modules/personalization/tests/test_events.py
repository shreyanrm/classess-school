"""profile.updated event emission: attributed, append-only, PII-free, gateway-
degrading; carries provisional traits with evidence + confidence.
"""

from __future__ import annotations

import uuid

from app.config import PersonalizationSettings
from app.consent_gate import PersonalizationConsent, TraitKind
from app.events import (
    PersonalizationEventEmitter,
    build_envelope,
    build_profile_updated_payload,
)
from app.infer import InferenceInput
from app.profile import project_profile


def _id() -> str:
    return str(uuid.uuid4())


def test_payload_carries_provisional_evidenced_traits(learner, rich_signals, adult_consent, asof):
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    profile = project_profile(inp, consents=[adult_consent], asof=asof)
    payload = build_profile_updated_payload(profile, trigger="fresh-signal")

    assert payload["provisional"] is True
    assert payload["trigger"] == "fresh-signal"
    assert payload["traits"], "the event must carry the inferred traits"
    for t in payload["traits"]:
        assert t["provisional"] is True
        assert t["evidence_signal_ids"], "every trait on the wire carries evidence"
        assert 0.0 <= t["confidence"] <= 1.0
        assert "explanation" in t


def test_envelope_is_attributed_and_pii_free(learner, rich_signals, adult_consent, asof):
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    profile = project_profile(inp, consents=[adult_consent], asof=asof)
    consent_ref = _id()
    payload = build_profile_updated_payload(profile)
    env = build_envelope(canonical_uuid=learner, consent_ref=consent_ref, payload=payload)

    assert env["canonical_uuid"] == learner
    assert env["consent_ref"] == consent_ref
    assert env["type"] == "profile.updated"
    assert env["schema_version"] == "v1"
    assert env["app"] == "school"
    # No PII keys anywhere.
    blob = str(env).lower()
    for forbidden in ("name", "email", "phone", "address"):
        assert forbidden not in blob


def test_pii_payload_is_rejected():
    """A payload with a PII-shaped key is refused at the boundary."""
    try:
        build_envelope(
            canonical_uuid=_id(), consent_ref=_id(),
            payload={"email": "leak"},
        )
    except ValueError:
        pass
    else:
        raise AssertionError("a PII-shaped payload must be rejected")


def test_emitter_degrades_to_append_only_sink(learner, rich_signals, adult_consent, asof):
    """With no gateway configured, events buffer to an in-memory append-only sink
    and the auth token is never required/hardcoded."""
    settings = PersonalizationSettings()  # nothing configured
    emitter = PersonalizationEventEmitter(settings)
    assert emitter.degraded

    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    profile = project_profile(inp, consents=[adult_consent], asof=asof)
    result = emitter.emit_profile_updated(profile, consent_ref=_id(), trigger="fresh-signal")
    assert result.delivered is False  # degraded, not delivered through a gateway
    assert len(emitter.buffered()) == 1
    # Append-only: a second emit appends, never replaces.
    emitter.emit_profile_updated(profile, consent_ref=_id(), trigger="revocation")
    assert len(emitter.buffered()) == 2


def test_revocation_emits_reduced_trait_set(learner, rich_signals, adult_consent, asof):
    """A revocation that clears traits is emitted as a profile.updated with the
    reduced (empty) trait set — append-only, never an in-place delete."""
    import dataclasses

    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    revoked = dataclasses.replace(adult_consent, revoked=True)
    cleared = project_profile(inp, consents=[revoked], asof=asof)
    payload = build_profile_updated_payload(cleared, trigger="revocation")
    assert payload["traits"] == []
    assert payload["trigger"] == "revocation"
