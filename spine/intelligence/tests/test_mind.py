"""Learned-representation tests — the per-learner cognitive fingerprint, the
governed (consent + purpose gated) faucet read, deterministic replay, and the
stable conditioning-payload shape.

INVARIANTS under test:
  - the representation is PII-FREE and derived ONLY from events,
  - the governed read enforces consent + purpose (a faucet, not bulk access),
  - replay over the same events is deterministic (same fingerprint out),
  - the conditioning payload shape is stable (pinned schema + field set).
"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.mind import (
    ALLOWED_CONDITIONING_PURPOSES,
    MIND_SCHEMA_VERSION,
    CognitiveFingerprint,
    ConditioningPayload,
    ConsentDenied,
    ConsentGrant,
    PurposeNotPermitted,
    assert_pii_free,
    build_conditioning_payload,
    build_fingerprint,
    derive_fingerprint,
    open_faucet,
)
from app.profile import build_profile

from .conftest import (
    CONSENT,
    LEARNER_A,
    LEARNER_B,
    NOW,
    T_EUCLID,
    T_FUNDTHM,
    T_IRRATIONAL,
    days_ago,
    indep,
    score_event,
    supported,
)


def _grant(subject: UUID, *purposes: str) -> ConsentGrant:
    return ConsentGrant(
        subject=subject,
        consent_ref=CONSENT,
        granted=True,
        purposes=frozenset(purposes),  # type: ignore[arg-type]
    )


def _independent_learner_events():
    return [indep(LEARNER_A, T_EUCLID, correct=True, difficulty=0.6, occurred_at=days_ago(i)) for i in range(5)]


def _support_dependent_events():
    # Succeeds only WITH help, then fails independently — the keystone pattern.
    return (
        [supported(LEARNER_B, T_EUCLID, correct=True, assistance_level="Coach", occurred_at=days_ago(i)) for i in range(4)]
        + [indep(LEARNER_B, T_EUCLID, correct=False, score=0.2, occurred_at=days_ago(1))]
    )


# ---------------------------------------------------------------------------
# Derivation: derived only from events, PII-free.
# ---------------------------------------------------------------------------
def test_fingerprint_is_keyed_by_opaque_uuid_only():
    fp = build_fingerprint(_independent_learner_events(), subject=LEARNER_A, asof=NOW)
    assert fp.canonical_uuid == LEARNER_A
    # Every event-id in the lineage is one of the synthetic opaque ids.
    assert fp.evidence_event_ids
    assert all(isinstance(e, UUID) for e in fp.evidence_event_ids)


def test_fingerprint_is_pii_free_structurally():
    """assert_pii_free must pass for any derived fingerprint: only opaque uuids
    in the allowed locations and bounded enum/version strings elsewhere."""
    for events, subject in (
        (_independent_learner_events(), LEARNER_A),
        (_support_dependent_events(), LEARNER_B),
    ):
        fp = build_fingerprint(events, subject=subject, asof=NOW)
        assert_pii_free(fp)  # raises on any leak


def test_pii_guard_catches_injected_free_text():
    """The guard is real: a smuggled free-form/contact-like string is rejected.

    ``model_construct`` bypasses validation, simulating a future field that
    accidentally smuggles a digit-bearing identifier into a band-shaped slot."""
    fp = build_fingerprint(_independent_learner_events(), subject=LEARNER_A, asof=NOW)
    tainted = fp.model_copy()
    object.__setattr__(tainted, "preferred_explanation_style", "learner-9876543210")
    with pytest.raises(ValueError):
        assert_pii_free(tainted)


def test_fingerprint_derived_only_from_profile_and_events():
    """derive_fingerprint over the profile reproduces build_fingerprint exactly
    when given the same events — the representation adds no outside input."""
    events = _support_dependent_events()
    profile = build_profile(events, subject=LEARNER_B, asof=NOW)
    a = derive_fingerprint(profile, events=events)
    b = build_fingerprint(events, subject=LEARNER_B, asof=NOW)
    assert a.model_dump() == b.model_dump()


# ---------------------------------------------------------------------------
# The signals actually distinguish learners.
# ---------------------------------------------------------------------------
def test_independence_profile_separates_independent_from_supported():
    fa = build_fingerprint(_independent_learner_events(), subject=LEARNER_A, asof=NOW)
    fb = build_fingerprint(_support_dependent_events(), subject=LEARNER_B, asof=NOW)
    assert fa.independence.tendency == "mostly-independent"
    assert fb.independence.tendency in ("mostly-supported", "mixed")
    assert fa.independence.independence_index > fb.independence.independence_index
    # The support-dependent learner shows the matching gap tendency + confidence.
    assert "support-dependency" in fb.gap_tendencies
    assert fb.confidence_pattern == "dips-under-self-reliance"
    assert fa.confidence_pattern == "transfers"


def test_explanation_style_follows_dominant_gap():
    # Conceptual struggle: weak even when supported -> concept-first lever.
    events = [
        supported(LEARNER_A, T_EUCLID, correct=False, score=0.1, assistance_level="Coach", occurred_at=days_ago(3)),
        supported(LEARNER_A, T_EUCLID, correct=False, score=0.15, assistance_level="Coach", occurred_at=days_ago(2)),
    ]
    fp = build_fingerprint(events, subject=LEARNER_A, asof=NOW)
    assert "conceptual" in fp.gap_tendencies
    assert fp.preferred_explanation_style == "concept-first"


def test_retention_params_shorten_half_life_on_recurring_retention_gaps():
    # Strong early independent success, then long-stale -> retention gap recurs.
    events = [indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(120)) for _ in range(3)]
    fp = build_fingerprint(events, subject=LEARNER_A, asof=NOW)
    if "retention" in fp.gap_tendencies:
        # Half-life is adjusted DOWN from the engine default (21 days) when
        # retention gaps recur — the per-learner forgetting adjustment.
        assert fp.retention.half_life_days < 21.0
    assert fp.retention.half_life_days > 0
    assert 0.0 <= fp.retention.retention_gap_recurrence <= 1.0


def test_pace_reads_more_deliberate_for_slow_attempts():
    events = [indep(LEARNER_A, T_EUCLID, correct=True, time_taken_ms=120_000, occurred_at=days_ago(i)) for i in range(3)]
    fp = build_fingerprint(events, subject=LEARNER_A, asof=NOW)
    assert fp.pace == "more-deliberate"


def test_empty_history_is_not_yet_evidenced_and_payload_degrades_gracefully():
    fp = build_fingerprint([], subject=LEARNER_A, asof=NOW)
    assert fp.independence.tendency == "not-yet-evidenced"
    assert fp.pace == "not-yet-evidenced"
    assert fp.confidence_pattern == "not-yet-evidenced"
    assert fp.preferred_explanation_style == "balanced"
    assert fp.gap_tendencies == {}
    # Still produces a well-formed payload through the faucet.
    payload = open_faucet(fp, purpose="instruction", consent=_grant(LEARNER_A, "instruction"))
    assert payload.tutor_directives  # always at least style + independence


# ---------------------------------------------------------------------------
# Deterministic replay.
# ---------------------------------------------------------------------------
def test_replay_is_deterministic_regardless_of_event_order():
    events = _support_dependent_events()
    a = build_fingerprint(events, subject=LEARNER_B, asof=NOW)
    b = build_fingerprint(list(reversed(events)), subject=LEARNER_B, asof=NOW)
    assert a.model_dump() == b.model_dump()


def test_recompute_over_same_events_is_idempotent():
    events = _independent_learner_events()
    first = build_fingerprint(events, subject=LEARNER_A, asof=NOW)
    second = build_fingerprint(list(events), subject=LEARNER_A, asof=NOW)
    assert first.model_dump() == second.model_dump()


# ---------------------------------------------------------------------------
# Governed read — consent + purpose gating (faucet, not bulk access).
# ---------------------------------------------------------------------------
def test_open_faucet_returns_payload_with_granted_consent_and_allowed_purpose():
    fp = build_fingerprint(_independent_learner_events(), subject=LEARNER_A, asof=NOW)
    payload = open_faucet(fp, purpose="instruction", consent=_grant(LEARNER_A, "instruction", "practice"))
    assert isinstance(payload, ConditioningPayload)
    assert payload.canonical_uuid == LEARNER_A
    assert payload.purpose == "instruction"


def test_open_faucet_refuses_when_consent_not_granted():
    fp = build_fingerprint(_independent_learner_events(), subject=LEARNER_A, asof=NOW)
    denied = ConsentGrant(subject=LEARNER_A, consent_ref=CONSENT, granted=False, purposes=frozenset({"instruction"}))
    with pytest.raises(ConsentDenied):
        open_faucet(fp, purpose="instruction", consent=denied)


def test_open_faucet_refuses_purpose_outside_consent():
    fp = build_fingerprint(_independent_learner_events(), subject=LEARNER_A, asof=NOW)
    # Consent granted, but only for practice — instruction is not covered.
    with pytest.raises(PurposeNotPermitted):
        open_faucet(fp, purpose="instruction", consent=_grant(LEARNER_A, "practice"))


def test_open_faucet_refuses_purpose_outside_allowed_set():
    fp = build_fingerprint(_independent_learner_events(), subject=LEARNER_A, asof=NOW)
    with pytest.raises(PurposeNotPermitted):
        open_faucet(fp, purpose="operations", consent=_grant(LEARNER_A, "operations"))  # type: ignore[arg-type]


def test_open_faucet_refuses_consent_for_a_different_subject():
    fp = build_fingerprint(_independent_learner_events(), subject=LEARNER_A, asof=NOW)
    # A grant scoped to a different learner must never unlock this subject.
    other = _grant(LEARNER_B, "instruction")
    with pytest.raises(ConsentDenied):
        open_faucet(fp, purpose="instruction", consent=other)


# ---------------------------------------------------------------------------
# Conditioning payload — stable shape.
# ---------------------------------------------------------------------------
EXPECTED_PAYLOAD_FIELDS = {
    "schema_version",
    "canonical_uuid",
    "purpose",
    "independence_tendency",
    "independence_index",
    "pace",
    "preferred_explanation_style",
    "confidence_pattern",
    "retention_half_life_days",
    "review_due_topic_count",
    "recurring_gap_types",
    "tutor_directives",
    "topic_count",
    "observation_count",
    "evidence_event_ids",
    "degraded",
    "degraded_reasons",
}


def test_conditioning_payload_shape_is_stable():
    fp = build_fingerprint(_support_dependent_events(), subject=LEARNER_B, asof=NOW)
    payload = build_conditioning_payload(fp, purpose="intervention")
    assert set(payload.model_dump().keys()) == EXPECTED_PAYLOAD_FIELDS
    assert payload.schema_version == MIND_SCHEMA_VERSION


def test_conditioning_payload_is_deterministic():
    fp = build_fingerprint(_support_dependent_events(), subject=LEARNER_B, asof=NOW)
    a = build_conditioning_payload(fp, purpose="instruction")
    b = build_conditioning_payload(fp, purpose="instruction")
    assert a.model_dump() == b.model_dump()


def test_conditioning_payload_carries_lineage_and_degrade_flag():
    fp = build_fingerprint(
        _independent_learner_events(), subject=LEARNER_A, asof=NOW,
        degraded_reasons=["clss.intelligence.dev.database_url"],
    )
    payload = build_conditioning_payload(fp, purpose="mastery")
    assert payload.evidence_event_ids == fp.evidence_event_ids
    assert payload.degraded is True
    assert "clss.intelligence.dev.database_url" in payload.degraded_reasons


def test_payload_recurring_gap_types_are_canonical_enum_tokens_only():
    fp = build_fingerprint(_support_dependent_events(), subject=LEARNER_B, asof=NOW)
    payload = build_conditioning_payload(fp, purpose="intervention")
    from app.models import GAP_TYPES
    assert all(g in GAP_TYPES for g in payload.recurring_gap_types)


def test_allowed_conditioning_purposes_are_a_subset_of_governed_purposes():
    # Each allowed conditioning purpose is a real, narrow set — no surprises.
    assert set(ALLOWED_CONDITIONING_PURPOSES) == {"instruction", "intervention", "mastery", "practice"}
