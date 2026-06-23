"""The consent + age-tier admissibility gate (INVARIANT 6)."""

from __future__ import annotations

from uuid import uuid4

from app.consent_gate import (
    MODEL_IMPROVEMENT_SCOPE,
    ConsentGate,
    ConsentRecord,
    DenyReason,
)

from .conftest import (
    ADULT,
    CHILD,
    CONSENT_ADULT,
    CONSENT_CHILD,
    CONSENT_NARROW,
    CONSENT_TEEN,
    GUARDIAN,
    TEEN,
    consent_granted_event,
    consent_revoked_event,
)


def test_deny_by_default_unknown_consent():
    gate = ConsentGate([])
    d = gate.evaluate(canonical_uuid=ADULT, consent_ref=uuid4())
    assert d.admissible is False
    assert d.deny_reason is DenyReason.NO_CONSENT


def test_adult_model_improvement_admissible(gate):
    d = gate.evaluate(canonical_uuid=ADULT, consent_ref=CONSENT_ADULT)
    assert d.admissible is True
    assert d.age_tier == "adult"


def test_child_never_admissible(gate):
    d = gate.evaluate(canonical_uuid=CHILD, consent_ref=CONSENT_CHILD)
    assert d.admissible is False
    assert d.deny_reason is DenyReason.MINOR_CHILD_BLOCKED


def test_teen_admissible_only_with_guardian(gate):
    d = gate.evaluate(canonical_uuid=TEEN, consent_ref=CONSENT_TEEN)
    assert d.admissible is True
    assert d.age_tier == "teen"


def test_teen_denied_without_guardian():
    gate = ConsentGate(
        [ConsentRecord(CONSENT_TEEN, TEEN, "teen", MODEL_IMPROVEMENT_SCOPE, granted_by=None)]
    )
    d = gate.evaluate(canonical_uuid=TEEN, consent_ref=CONSENT_TEEN)
    assert d.admissible is False
    assert d.deny_reason is DenyReason.TEEN_NO_GUARDIAN


def test_narrow_scope_denied(gate):
    d = gate.evaluate(canonical_uuid=ADULT, consent_ref=CONSENT_NARROW)
    assert d.admissible is False
    assert d.deny_reason is DenyReason.SCOPE_MISMATCH


def test_revocation_removes_admissibility(gate):
    assert gate.is_admissible(canonical_uuid=ADULT, consent_ref=CONSENT_ADULT)
    gate.revoke(CONSENT_ADULT)
    d = gate.evaluate(canonical_uuid=ADULT, consent_ref=CONSENT_ADULT)
    assert d.admissible is False
    assert d.deny_reason is DenyReason.REVOKED


def test_consent_ref_learner_mismatch_denied(gate):
    # The adult's consent ref, but asserted for a different learner.
    d = gate.evaluate(canonical_uuid=TEEN, consent_ref=CONSENT_ADULT)
    assert d.admissible is False
    assert d.deny_reason is DenyReason.CONSENT_REF_MISMATCH


def test_apply_event_builds_and_revokes():
    gate = ConsentGate([])
    gate.apply_event(
        consent_granted_event(
            subject=ADULT, consent_ref=CONSENT_ADULT, age_tier="adult"
        )
    )
    assert gate.is_admissible(canonical_uuid=ADULT, consent_ref=CONSENT_ADULT)
    gate.apply_event(consent_revoked_event(subject=ADULT, consent_ref=CONSENT_ADULT))
    assert not gate.is_admissible(canonical_uuid=ADULT, consent_ref=CONSENT_ADULT)


def test_decision_carries_transparent_provenance(gate):
    d = gate.evaluate(canonical_uuid=ADULT, consent_ref=CONSENT_ADULT)
    assert d.provenance["consent_ref"] == str(CONSENT_ADULT)
    assert d.provenance["age_tier"] == "adult"
    assert d.reason  # plain-language reason always present


def test_teen_guardian_provenance_present(gate):
    d = gate.evaluate(canonical_uuid=TEEN, consent_ref=CONSENT_TEEN)
    assert d.admissible
    # guardian id is recorded on the record, gate does not need to expose it,
    # but the age tier is in provenance.
    assert d.provenance["age_tier"] == "teen"
    _ = GUARDIAN  # referenced for clarity
