"""The consent + AGE-TIER gate: denied-by-default, over-tier denied, a minor
tier infers strictly less than an adult.
"""

from __future__ import annotations

import uuid

from app.consent_gate import (
    InferenceDenied,
    PersonalizationConsent,
    TraitKind,
    evaluate_inference,
    permitted_traits,
    require_inference,
    tier_policy,
)
from app.infer import InferenceInput, infer_profile


def _id() -> str:
    return str(uuid.uuid4())


def test_denied_by_default_no_consent(learner, asof):
    result = evaluate_inference(
        subject=learner, trait=TraitKind.INTEREST, consents=[], asof=asof
    )
    assert not result.allowed
    assert "no personalization consent" in result.reason.lower()


def test_revoked_consent_denies(learner, asof):
    consent = PersonalizationConsent(
        consent_id=_id(), subject=learner, age_tier="adult",
        scopes=frozenset({"profiling"}), revoked=True,
    )
    result = evaluate_inference(
        subject=learner, trait=TraitKind.INTEREST, consents=[consent], asof=asof
    )
    assert not result.allowed
    assert "revoked" in result.reason.lower() or "expired" in result.reason.lower()


def test_over_tier_inference_denied(learner, asof):
    """A child tier requesting learning-style (an adult-only trait) is DENIED."""
    child = PersonalizationConsent(
        consent_id=_id(), subject=learner, age_tier="child",
        scopes=frozenset({"profiling"}),
    )
    result = evaluate_inference(
        subject=learner, trait=TraitKind.LEARNING_STYLE, consents=[child], asof=asof
    )
    assert not result.allowed
    assert "over-tier" in result.reason.lower() or "legally permits" in result.reason.lower()

    # require_ raises on the over-tier inference.
    try:
        require_inference(
            subject=learner, trait=TraitKind.LEARNING_STYLE, consents=[child], asof=asof
        )
    except InferenceDenied:
        pass
    else:
        raise AssertionError("over-tier inference must raise InferenceDenied")


def test_tier_ceilings_are_strictly_nested():
    """child ⊂ teen ⊂ adult — a more protected tier permits strictly fewer."""
    child = tier_policy("child").permitted
    teen = tier_policy("teen").permitted
    adult = tier_policy("adult").permitted
    assert child < teen < adult  # strict subsets
    # The child tier excludes the deepest inferences.
    assert TraitKind.LEARNING_STYLE not in child
    assert TraitKind.GOAL not in child
    assert TraitKind.STRENGTH not in child
    # The adult tier permits everything.
    assert adult == frozenset(TraitKind)


def test_minor_tier_infers_strictly_less(learner, rich_signals, asof):
    """Same signals, a child vs an adult consent: the child profile is a strict
    subset of the adult profile and is smaller."""
    child = PersonalizationConsent(
        consent_id=_id(), subject=learner, age_tier="child",
        scopes=frozenset({"profiling"}),
    )
    adult = PersonalizationConsent(
        consent_id=_id(), subject=learner, age_tier="adult",
        scopes=frozenset({"profiling"}),
    )
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    child_profile = infer_profile(inp, consents=[child], asof=asof)
    adult_profile = infer_profile(inp, consents=[adult], asof=asof)

    child_kinds = {t.kind for t in child_profile.traits}
    adult_kinds = {t.kind for t in adult_profile.traits}
    assert child_kinds < adult_kinds, "a minor must infer strictly less than an adult"
    # The deep inferences must be absent for the child and recorded as denied.
    assert TraitKind.LEARNING_STYLE not in child_kinds
    denied_kinds = {k for k, _ in child_profile.denied_traits}
    assert "learning_style" in denied_kinds


def test_tier_caps_confidence(learner, rich_signals, asof):
    """A more protected tier holds a more provisional read (lower confidence cap)."""
    child = PersonalizationConsent(
        consent_id=_id(), subject=learner, age_tier="child",
        scopes=frozenset({"profiling"}),
    )
    adult = PersonalizationConsent(
        consent_id=_id(), subject=learner, age_tier="adult",
        scopes=frozenset({"profiling"}),
    )
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    child_profile = infer_profile(inp, consents=[child], asof=asof)
    adult_profile = infer_profile(inp, consents=[adult], asof=asof)

    child_interest = child_profile.trait(TraitKind.INTEREST).confidence
    adult_interest = adult_profile.trait(TraitKind.INTEREST).confidence
    assert child_interest <= tier_policy("child").max_confidence
    assert child_interest <= adult_interest


def test_grant_can_narrow_within_tier(learner, asof):
    """A grant naming a subset narrows the permitted set; the tier never widens it."""
    consent = PersonalizationConsent(
        consent_id=_id(), subject=learner, age_tier="adult",
        scopes=frozenset({"profiling"}),
        traits=frozenset({TraitKind.INTEREST}),  # only interest
    )
    assert permitted_traits(consent) == frozenset({TraitKind.INTEREST})
    assert evaluate_inference(
        subject=learner, trait=TraitKind.INTEREST, consents=[consent], asof=asof
    ).allowed
    assert not evaluate_inference(
        subject=learner, trait=TraitKind.GOAL, consents=[consent], asof=asof
    ).allowed


def test_scope_must_match(learner, asof):
    """A grant for preferences-hints does not satisfy a profiling inference."""
    consent = PersonalizationConsent(
        consent_id=_id(), subject=learner, age_tier="adult",
        scopes=frozenset({"preferences-hints"}),
    )
    result = evaluate_inference(
        subject=learner, trait=TraitKind.INTEREST, consents=[consent],
        scope="profiling", asof=asof,
    )
    assert not result.allowed
    assert "scope" in result.reason.lower()
