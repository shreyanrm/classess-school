"""Parent feedback: celebration/growth/next-step generated FROM real signals via
generate-and-verify — grounded, confidence-gated, never canned, never a number."""

from __future__ import annotations

from app.parent_feedback import (
    ParentFeedbackGenerator,
    ProgressSignal,
    SignalKind,
)


CHILD = "9999aaaa-0000-4000-8000-000000000040"


def _gen() -> ParentFeedbackGenerator:
    return ParentFeedbackGenerator()


def test_feedback_is_grounded_in_real_signals():
    signals = [
        ProgressSignal(SignalKind.STRENGTH, "fractions", "explained their reasoning clearly", 0.9),
        ProgressSignal(SignalKind.GROWTH_AREA, "spelling", "is building confidence with longer words", 0.8),
        ProgressSignal(SignalKind.HABIT, "reading", "reads most evenings", 0.75),
    ]
    fb = _gen().generate(child_uuid=CHILD, signals=signals)
    assert fb.celebration is not None and fb.celebration.verified
    assert fb.growth is not None
    assert fb.next_step is not None
    # Grounded: the win references the real signal's descriptor.
    assert fb.celebration.grounded_in == "explained their reasoning clearly"
    assert "fractions" in fb.celebration.text


def test_a_part_with_no_supporting_signal_is_withheld_not_fabricated():
    # Only a growth signal -> no celebration to ground; it is honestly withheld.
    signals = [
        ProgressSignal(SignalKind.GROWTH_AREA, "spelling", "is still finding long words tricky", 0.8),
    ]
    fb = _gen().generate(child_uuid=CHILD, signals=signals)
    assert fb.celebration is None
    assert any("celebration" in note for note in fb.withheld_notes)
    assert fb.growth is not None


def test_low_confidence_signal_fails_the_verification_gate():
    signals = [
        ProgressSignal(SignalKind.STRENGTH, "fractions", "maybe improving", 0.2),
    ]
    fb = _gen().generate(child_uuid=CHILD, signals=signals)
    assert fb.celebration is None  # below the confidence gate -> withheld.
    assert any("confidence gate" in note for note in fb.withheld_notes)


def test_feedback_carries_no_raw_number_or_percentage():
    signals = [
        ProgressSignal(SignalKind.STRENGTH, "fractions", "kept going through hard problems", 0.95),
        ProgressSignal(SignalKind.GROWTH_AREA, "spelling", "is building confidence", 0.85),
        ProgressSignal(SignalKind.HABIT, "reading", "reads most evenings", 0.7),
    ]
    fb = _gen().generate(child_uuid=CHILD, signals=signals)
    for part in fb.parts:
        assert "%" not in part.text
        assert not any(ch.isdigit() for ch in part.text)


def test_output_is_specific_to_signals_not_one_canned_string():
    a = _gen().generate(
        child_uuid=CHILD,
        signals=[ProgressSignal(SignalKind.STRENGTH, "algebra", "spotted the pattern", 0.9)],
    )
    b = _gen().generate(
        child_uuid=CHILD,
        signals=[ProgressSignal(SignalKind.STRENGTH, "history", "made a strong argument", 0.9)],
    )
    assert a.celebration is not None and b.celebration is not None
    assert a.celebration.text != b.celebration.text  # composed from the signal.
