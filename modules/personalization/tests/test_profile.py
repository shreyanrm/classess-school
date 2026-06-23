"""The profile projection: idempotent replay, revocation clears inferred traits,
PII never enters the profile.
"""

from __future__ import annotations

import uuid
from dataclasses import replace

from app.consent_gate import PersonalizationConsent, TraitKind
from app.infer import InferenceInput, Signal, SignalKind
from app.profile import PersonalizationProfile, clear_on_revocation, project_profile, replay


def _id() -> str:
    return str(uuid.uuid4())


def test_projection_is_idempotent(learner, rich_signals, adult_consent, asof):
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    a = project_profile(inp, consents=[adult_consent], asof=asof)
    b = project_profile(inp, consents=[adult_consent], asof=asof)
    # Same inputs -> same traits (kind+value+confidence+evidence), same order.
    assert [(t.kind, t.value, t.confidence) for t in a.traits] == [
        (t.kind, t.value, t.confidence) for t in b.traits
    ]
    assert a.source_signal_ids == b.source_signal_ids


def test_replay_updates_on_fresh_signal(learner, topic_math, adult_consent, asof):
    base = [Signal(signal_id=_id(), kind=SignalKind.TOPIC_ENGAGEMENT, subject_id=topic_math, weight=1.0)]
    fresh = base + [
        Signal(signal_id=_id(), kind=SignalKind.TOPIC_ENGAGEMENT, subject_id=topic_math, weight=2.0)
        for _ in range(4)
    ]
    before = replay(learner, base, consents=[adult_consent], asof=asof)
    after = replay(learner, fresh, consents=[adult_consent], asof=asof)
    assert after.trait(TraitKind.INTEREST).confidence > before.trait(TraitKind.INTEREST).confidence


def test_revocation_clears_inferred_traits(learner, rich_signals, adult_consent, asof):
    """Revoking consent and replaying clears the inferred traits."""
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    granted = project_profile(inp, consents=[adult_consent], asof=asof)
    assert granted.traits, "with consent, traits are inferred"

    revoked_consent = replace(adult_consent, revoked=True)
    cleared = clear_on_revocation(granted, inp, consents=[revoked_consent], asof=asof)
    assert cleared.traits == (), "revocation must clear all inferred traits"
    assert cleared.is_empty()


def test_narrowing_consent_clears_only_unpermitted(learner, rich_signals, adult_consent, asof):
    """Narrowing consent to one trait leaves only that trait; the rest are cleared."""
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    full = project_profile(inp, consents=[adult_consent], asof=asof)
    assert len(full.trait_kinds) > 1

    narrowed = replace(adult_consent, traits=frozenset({TraitKind.INTEREST}))
    after = project_profile(inp, consents=[narrowed], asof=asof)
    assert after.trait_kinds == frozenset({TraitKind.INTEREST})


def test_profile_is_pii_free(learner, rich_signals, adult_consent, asof):
    """The projected profile carries only opaque ids and behavioural reads.

    Trait values are opaque topic ids / enumerated values; nothing in the
    projection holds a name/email/free-text-about-the-person field.
    """
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    profile = project_profile(inp, consents=[adult_consent], asof=asof)

    # No PII-shaped field on the dataclass.
    fields = set(PersonalizationProfile.__dataclass_fields__.keys())
    for forbidden in ("name", "email", "phone", "dob", "address"):
        assert not any(forbidden in f for f in fields)

    # The subject is the opaque uuid we passed (never derived from PII here).
    assert profile.subject == learner
    # Trait values are the opaque topic ids / enumerated values — no free text.
    topic_ids = {s.subject_id for s in rich_signals if s.subject_id}
    enumerated = {"video", "reading", "interactive", "audio", "worked_example",
                  "fast", "steady", "deliberate", "exam-readiness"}
    for trait in profile.traits:
        assert trait.value in topic_ids or trait.value in enumerated


def test_no_consent_yields_empty_profile(learner, rich_signals, asof):
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    profile = project_profile(inp, consents=[], asof=asof)
    assert profile.is_empty()
