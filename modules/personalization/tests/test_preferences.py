"""Surface hints: raw inference internals never leak to a learner; hints are
calm plain language; gated by the preferences-hints scope.
"""

from __future__ import annotations

import dataclasses
import uuid

from app.consent_gate import PersonalizationConsent, TraitKind
from app.infer import InferenceInput
from app.preferences import Hint, SurfaceHints, assert_brand_clean, to_surface_hints
from app.profile import project_profile


def _id() -> str:
    return str(uuid.uuid4())


def test_hints_carry_no_raw_internals(learner, rich_signals, adult_consent, asof):
    """A Hint exposes value + a plain-language reason — never confidence or
    evidence ids."""
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    profile = project_profile(inp, consents=[adult_consent], asof=asof)
    hints = to_surface_hints(profile, consents=[adult_consent], asof=asof)

    hint_fields = set(Hint.__dataclass_fields__.keys())
    assert "confidence" not in hint_fields
    assert "evidence_signal_ids" not in hint_fields
    assert hint_fields == {"kind", "value", "why"}
    assert hints.suggested_subjects, "a confident profile should yield subject hints"


def test_hints_are_brand_clean(learner, rich_signals, adult_consent, asof):
    """No emoji, no exclamation marks in the learner-facing copy."""
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    profile = project_profile(inp, consents=[adult_consent], asof=asof)
    hints = to_surface_hints(profile, consents=[adult_consent], asof=asof)
    for h in hints.suggested_subjects:
        assert_brand_clean(h.why)
        assert "!" not in h.why
    if hints.suggested_goal:
        assert_brand_clean(hints.suggested_goal.why)
    if hints.suggested_pace:
        assert_brand_clean(hints.suggested_pace.why)


def test_brand_guard_rejects_exclamation():
    try:
        Hint(kind="subject", value="x", why="Great choice!")
    except ValueError:
        pass
    else:
        raise AssertionError("exclamation marks must be rejected in product copy")


def test_hints_gated_by_preferences_scope(learner, rich_signals, asof):
    """Profiling consent without the preferences-hints scope yields no hints."""
    profiling_only = PersonalizationConsent(
        consent_id=_id(), subject=learner, age_tier="adult",
        scopes=frozenset({"profiling"}),  # no preferences-hints scope
    )
    inp = InferenceInput(subject=learner, signals=tuple(rich_signals))
    profile = project_profile(inp, consents=[profiling_only], asof=asof)
    assert profile.traits  # the profile itself is inferred
    hints = to_surface_hints(profile, consents=[profiling_only], asof=asof)
    assert hints.is_empty(), "hints require the preferences-hints scope"


def test_low_confidence_trait_is_not_surfaced(learner, topic_math, asof):
    """A single weak signal is below the hint floor and is withheld."""
    from app.infer import Signal, SignalKind

    consent = PersonalizationConsent(
        consent_id=_id(), subject=learner, age_tier="adult",
        scopes=frozenset({"profiling", "preferences-hints"}),
    )
    weak = [Signal(signal_id=_id(), kind=SignalKind.TOPIC_ENGAGEMENT, subject_id=topic_math, weight=0.2)]
    inp = InferenceInput(subject=learner, signals=tuple(weak))
    profile = project_profile(inp, consents=[consent], asof=asof)
    hints = to_surface_hints(profile, consents=[consent], asof=asof)
    assert hints.is_empty(), "a barely-formed read is not shown as a suggestion"
