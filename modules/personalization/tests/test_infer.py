"""Inference works from BEHAVIOURAL SIGNALS alone — never a questionnaire.

These assert the core claim of the module: we get to know the user WITHOUT
asking. Every produced trait carries evidence + a confidence and is provisional.
"""

from __future__ import annotations

import inspect

from app import infer as infer_mod
from app.consent_gate import TraitKind
from app.infer import (
    InferenceInput,
    InferredProfile,
    InferredTrait,
    Signal,
    SignalKind,
    infer_profile,
)


def test_no_questionnaire_input_anywhere():
    """There is NO place to pass an explicit questionnaire answer.

    The signal kinds and the inference input expose only behavioural inputs and
    light onboarding choices — no free-text "tell us about yourself" field.
    """
    kinds = {k.value for k in SignalKind}
    assert "questionnaire" not in " ".join(kinds)
    assert "questionnaire_answer" not in kinds

    # The inference input dataclass exposes only signals + onboarding_choices.
    fields = set(InferenceInput.__dataclass_fields__.keys())
    assert fields == {"subject", "signals", "onboarding_choices"}

    # No source symbol mentions a questionnaire as an input mechanism.
    src = inspect.getsource(infer_mod)
    assert "questionnaire" in src.lower()  # only ever mentioned to forbid it
    # ...and only in the negative ("never from an explicit questionnaire").
    assert "never from an explicit questionnaire" in src.lower()


def test_infers_from_signals_alone(learner, rich_signals, adult_consent, asof):
    profile = infer_profile(
        InferenceInput(subject=learner, signals=tuple(rich_signals)),
        consents=[adult_consent],
        asof=asof,
    )
    assert isinstance(profile, InferredProfile)
    assert profile.traits, "behavioural signals alone must produce traits"
    # The adult tier should surface multiple distinct trait kinds.
    kinds = {t.kind for t in profile.traits}
    assert TraitKind.INTEREST in kinds
    assert TraitKind.PREFERRED_SUBJECT in kinds
    assert TraitKind.STRENGTH in kinds
    assert TraitKind.LEARNING_STYLE in kinds


def test_every_trait_has_evidence_and_confidence(learner, rich_signals, adult_consent, asof):
    profile = infer_profile(
        InferenceInput(subject=learner, signals=tuple(rich_signals)),
        consents=[adult_consent],
        asof=asof,
    )
    for trait in profile.traits:
        assert trait.evidence_signal_ids, "a trait must link to evidence signals"
        assert 0.0 <= trait.confidence <= 1.0
        assert trait.explanation.startswith("inferred because") or "inferred" in trait.explanation
        assert trait.provisional is True


def test_trait_without_evidence_is_rejected():
    """A trait cannot be constructed without evidence — evidence over assertion."""
    try:
        InferredTrait(
            kind=TraitKind.INTEREST,
            value="x",
            confidence=0.5,
            evidence_signal_ids=(),
            explanation="inferred because…",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("a trait with no evidence must be rejected")


def test_trait_cannot_be_marked_permanent():
    """provisional=False is rejected — a trait is never a permanent label."""
    try:
        InferredTrait(
            kind=TraitKind.INTEREST,
            value="x",
            confidence=0.5,
            evidence_signal_ids=("e1",),
            explanation="inferred because…",
            provisional=False,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("a trait must never be permanent")


def test_more_evidence_raises_confidence(learner, topic_math, adult_consent, asof):
    """A trait is provisional and strengthens with corroborating fresh signal."""
    def signals(n: int):
        return tuple(
            Signal(signal_id=f"s{i}", kind=SignalKind.TOPIC_ENGAGEMENT, subject_id=topic_math, weight=1.0)
            for i in range(n)
        )

    light = infer_profile(InferenceInput(subject=learner, signals=signals(1)), consents=[adult_consent], asof=asof)
    heavy = infer_profile(InferenceInput(subject=learner, signals=signals(6)), consents=[adult_consent], asof=asof)
    lc = light.trait(TraitKind.INTEREST).confidence
    hc = heavy.trait(TraitKind.INTEREST).confidence
    assert hc > lc
    assert hc < 1.0, "confidence never reaches certainty — always provisional"


def test_onboarding_choice_is_a_light_tap_not_a_questionnaire(learner, goal_choice, adult_consent, asof):
    """A light onboarding goal-tap feeds inference as a behavioural choice."""
    profile = infer_profile(
        InferenceInput(subject=learner, onboarding_choices=(goal_choice,)),
        consents=[adult_consent],
        asof=asof,
    )
    goal = profile.trait(TraitKind.GOAL)
    assert goal is not None
    assert goal.value == "exam-readiness"
    assert goal.evidence_signal_ids  # the tap is the evidence
