"""Capture: events -> PII-free, consent-stamped learning signals (INVARIANT 1/2/6)."""

from __future__ import annotations

import pytest

from app.capture import (
    TASK_GAP_CLASSIFY,
    TASK_MASTERY_PREDICT,
    LearningSignal,
    PiiLeakError,
    SignalCapture,
    assert_pii_free,
)

from .conftest import (
    ADULT,
    CHILD,
    CONSENT_ADULT,
    CONSENT_CHILD,
    TOPIC,
    attempt_event,
    mastery_event,
)


def test_attempt_becomes_mastery_signal(gate):
    cap = SignalCapture(gate)
    signals = cap.capture_event(attempt_event(correct=True))
    assert len(signals) == 1
    s = signals[0]
    assert s.task_class == TASK_MASTERY_PREDICT
    assert s.output == "correct"
    assert s.reward == 1.0
    assert s.admissible is True


def test_confirmed_gap_becomes_gap_signal(gate):
    cap = SignalCapture(gate)
    signals = cap.capture_event(mastery_event(gap_type="procedural", gap_confirmed=True))
    classes = {s.task_class for s in signals}
    assert TASK_GAP_CLASSIFY in classes
    assert TASK_MASTERY_PREDICT in classes


def test_unconfirmed_gap_is_not_labelled(gate):
    cap = SignalCapture(gate)
    signals = cap.capture_event(mastery_event(gap_type="procedural", gap_confirmed=False))
    assert all(s.task_class != TASK_GAP_CLASSIFY for s in signals)


def test_signal_carries_only_opaque_uuid(gate):
    cap = SignalCapture(gate)
    s = cap.capture_event(attempt_event())[0]
    # The canonical uuid is opaque; no PII fields exist on the signal at all.
    assert s.canonical_uuid == ADULT
    assert_pii_free(s.input)
    assert_pii_free(s.output)


def test_pii_in_signal_is_refused():
    with pytest.raises(PiiLeakError):
        LearningSignal(
            signal_id="x",
            canonical_uuid=ADULT,
            task_class=TASK_MASTERY_PREDICT,
            input="learner Ravi Kumar attempted topic",
            output="correct",
            reward=1.0,
            consent_ref=CONSENT_ADULT,
            age_tier="adult",
            admissible=True,
        )


def test_pii_email_in_signal_is_refused():
    with pytest.raises(PiiLeakError):
        LearningSignal(
            signal_id="x",
            canonical_uuid=ADULT,
            task_class=TASK_MASTERY_PREDICT,
            input="contact parent at mom@example.com",
            output="correct",
            reward=1.0,
            consent_ref=CONSENT_ADULT,
            age_tier="adult",
            admissible=True,
        )


def test_child_signal_is_inadmissible(gate):
    cap = SignalCapture(gate)
    s = cap.capture_event(
        attempt_event(subject=CHILD, consent_ref=CONSENT_CHILD)
    )[0]
    assert s.admissible is False
    assert s.meta.get("deny_reason")


def test_admissible_signals_filters_inadmissible(gate):
    cap = SignalCapture(gate)
    events = [
        attempt_event(subject=ADULT, consent_ref=CONSENT_ADULT),
        attempt_event(subject=CHILD, consent_ref=CONSENT_CHILD),
    ]
    admissible = cap.admissible_signals(events)
    assert all(s.canonical_uuid == ADULT for s in admissible)
    assert len(admissible) == 1


def test_unknown_event_type_yields_nothing(gate):
    cap = SignalCapture(gate)
    ev = attempt_event()
    ev["type"] = "consent.granted"
    assert cap.capture_event(ev) == []


def test_ontology_ids_not_treated_as_pii(gate):
    cap = SignalCapture(gate)
    s = cap.capture_event(attempt_event())[0]
    assert str(TOPIC) in s.input  # opaque ontology id is fine
