"""The governed read view + the engine's event emission — the live-circuit wiring.

Exercises what crosses the gateway: the read view foregrounds independent-vs-
supported mastery and a NAMED gap, in plain language, evidence-linked, never
leaking the scalar; and the emitter emits mastery.updated / gap.detected /
gap.resolved from REAL events, idempotently and through the (degraded) sink.
"""

from __future__ import annotations

import pytest

from app.config import IntelligenceSettings
from app.profile import build_profile
from app.read import (
    IntelligenceEmitter,
    LearnerReadView,
    assert_no_scalar,
    read_view,
    view_from_profile,
)

from .conftest import (
    CONSENT,
    LEARNER_A,
    NOW,
    T_EUCLID,
    days_ago,
    indep,
    score_event,
    supported,
)

CONSENT_REF = str(CONSENT)


# --- the read view ---------------------------------------------------------
def test_independent_history_reads_independent_with_plain_language():
    events = [indep(LEARNER_A, T_EUCLID, occurred_at=days_ago(i), difficulty=0.6) for i in range(4)]
    view = read_view(events, subject=LEARNER_A, asof=NOW)
    t = view.topic(str(T_EUCLID))
    assert t is not None
    assert t.independence == "independent"
    assert t.plain_language == "you can do this independently"
    # Every item links to its evidence — no opaque claim.
    assert t.source_event_ids
    assert t.observation_count == 4


def test_supported_only_history_reads_support_dependent_and_names_the_gap():
    """THE KEYSTONE: success only with help reads support-dependent AND surfaces a
    NAMED, confirmed support-dependency gap with its evidence lineage."""
    events = [
        supported(LEARNER_A, T_EUCLID, correct=True, assistance_level="Coach",
                  occurred_at=days_ago(i), difficulty=0.6)
        for i in range(4)
    ]
    view = read_view(events, subject=LEARNER_A, asof=NOW)
    t = view.topic(str(T_EUCLID))
    assert t is not None
    assert t.independence == "support-dependent"
    gap_types = {g.gap_type for g in t.gaps if g.confirmed}
    assert "support-dependency" in gap_types
    sd = next(g for g in t.gaps if g.gap_type == "support-dependency")
    assert sd.confirmed is True
    assert sd.evidence_event_ids  # evidence-linked
    assert "fade" in sd.plain_language.lower()  # plain-language "what to do"


def test_view_never_leaks_a_scalar():
    """No number / percent / formula in any learner-facing string in the view."""
    events = [indep(LEARNER_A, T_EUCLID, occurred_at=days_ago(i)) for i in range(3)]
    view = read_view(events, subject=LEARNER_A, asof=NOW)
    for t in view.topics:
        assert_no_scalar(t.plain_language)  # constructor already guards; assert again
        for g in t.gaps:
            assert not any(ch.isdigit() for ch in g.plain_language)


def test_assert_no_scalar_rejects_numbers():
    with pytest.raises(ValueError):
        assert_no_scalar("you scored 80%")


def test_view_is_deterministic():
    events = [indep(LEARNER_A, T_EUCLID, occurred_at=days_ago(i)) for i in range(3)]
    a = read_view(events, subject=LEARNER_A, asof=NOW)
    b = read_view(events, subject=LEARNER_A, asof=NOW)
    assert a == b


def test_degraded_reasons_pass_through_for_fallback_affordance():
    events = [indep(LEARNER_A, T_EUCLID, occurred_at=days_ago(i)) for i in range(2)]
    profile = build_profile(events, subject=LEARNER_A, asof=NOW,
                            degraded_reasons=["clss.intelligence.dev.gateway_url"])
    view = view_from_profile(profile)
    assert "clss.intelligence.dev.gateway_url" in view.degraded_reasons


# --- event emission --------------------------------------------------------
def _degraded_emitter() -> IntelligenceEmitter:
    # No gateway/sink configured -> degraded in-memory append-only sink.
    return IntelligenceEmitter(IntelligenceSettings())


def test_emits_mastery_updated_and_named_gap_from_real_events():
    events = [
        supported(LEARNER_A, T_EUCLID, correct=True, assistance_level="Coach",
                  occurred_at=days_ago(i), difficulty=0.6)
        for i in range(4)
    ]
    view = read_view(events, subject=LEARNER_A, asof=NOW)
    em = _degraded_emitter()
    emitted = em.emit_for_view(view, consent_ref=CONSENT_REF)
    types = [e.envelope["type"] for e in emitted]
    assert "mastery.updated" in types
    assert "gap.detected" in types
    # Every emitted event is consent-stamped + evidence-linked + PII-free.
    for e in emitted:
        env = e.envelope
        assert env["consent_ref"] == CONSENT_REF
        assert env["canonical_uuid"] == str(LEARNER_A)
        assert env["payload"]["source_event_ids"]
        assert e.delivered is False  # degraded sink
        assert "degraded" in e.sink


def test_unconfirmed_gap_is_never_emitted_as_detected():
    """A single bad score is a prompt-to-reassess, never a confirmed judgment —
    so it is never emitted as gap.detected."""
    events = [indep(LEARNER_A, T_EUCLID, correct=False, occurred_at=NOW)]
    view = read_view(events, subject=LEARNER_A, asof=NOW)
    em = _degraded_emitter()
    emitted = em.emit_for_view(view, consent_ref=CONSENT_REF)
    assert all(e.envelope["type"] != "gap.detected" for e in emitted)


def test_emission_is_idempotent_against_previous():
    events = [indep(LEARNER_A, T_EUCLID, occurred_at=days_ago(i)) for i in range(4)]
    view = read_view(events, subject=LEARNER_A, asof=NOW)
    em = _degraded_emitter()
    first = em.emit_for_view(view, consent_ref=CONSENT_REF)
    assert first  # something emitted on the first read
    # Re-emitting the identical view against itself changes nothing.
    again = em.emit_for_view(view, consent_ref=CONSENT_REF, previous=view)
    assert again == []


def test_resolving_a_gap_emits_gap_resolved():
    """Support-dependency confirmed, then a run of independent successes clears it
    -> a gap.resolved event, append-only (never a mutation)."""
    supported_events = [
        supported(LEARNER_A, T_EUCLID, correct=True, assistance_level="Coach",
                  occurred_at=days_ago(20 - i), difficulty=0.6)
        for i in range(4)
    ]
    before = read_view(supported_events, subject=LEARNER_A, asof=NOW)
    assert any(
        g.gap_type == "support-dependency" and g.confirmed
        for t in before.topics for g in t.gaps
    )
    # Now the learner demonstrates independently and recently.
    after_events = supported_events + [
        indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(i), difficulty=0.6)
        for i in range(4)
    ]
    after = read_view(after_events, subject=LEARNER_A, asof=NOW)
    em = _degraded_emitter()
    emitted = em.emit_for_view(after, consent_ref=CONSENT_REF, previous=before)
    resolved = [e for e in emitted if e.envelope["type"] == "gap.resolved"]
    assert any(e.envelope["payload"]["gap_type"] == "support-dependency" for e in resolved)
