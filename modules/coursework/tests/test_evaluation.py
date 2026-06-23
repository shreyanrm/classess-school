"""The CORE evaluation engine — the existential-correctness rules.

These tests pin the non-negotiables:
  - consequential marks are NEVER auto-final (PERMISSION LADDER),
  - poor handwriting/scan NEVER reduces a mark (flags review),
  - preventive mode is helping, never a consequential mark,
  - non-high bands force needs_human_review,
  - a deterministic objective check works without an LLM.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.contracts import AnswerState, EvaluationConfidenceBand, EvaluationMode
from app.evaluation import (
    EvaluationEngine,
    ResponseInput,
    SubmissionInput,
    confirm_mark,
    is_provisional_auto,
)


class _AgreeingSecondModel:
    """A stand-in second model that agrees with high confidence — lets us prove
    the HIGH-band / provisional-auto path without a live provider."""

    def cross_check(self, *, task_class, content):
        return (True, 0.97)


def _objective_submission(expression: str, answer: float, *, consequential: bool = True):
    return SubmissionInput(
        submission_ref=uuid4(),
        scored_subject=uuid4(),
        responses=[ResponseInput(question_ref=uuid4(), expression=expression, learner_answer=answer)],
        consequential=consequential,
    )


def test_objective_correct_no_second_model_is_provisional_not_final():
    # No second model => the gate closes on the cross-check; even a correct
    # deterministic answer is MIDDLE (review), never standing alone.
    eng = EvaluationEngine()
    out = eng.post_submission(_objective_submission("3*4", 12.0))
    resp = out.responses[0]
    assert resp.answer_state is AnswerState.CORRECT
    assert resp.confidence_band is EvaluationConfidenceBand.MIDDLE
    assert resp.needs_human_review is True
    assert out.marking_gate.final is False


def test_objective_correct_with_second_model_is_high_provisional_auto():
    eng = EvaluationEngine(second_model=_AgreeingSecondModel())
    out = eng.post_submission(_objective_submission("3*4", 12.0))
    resp = out.responses[0]
    assert resp.confidence_band is EvaluationConfidenceBand.HIGH
    assert resp.needs_human_review is False
    # The mark is still NOT final — high confidence is provisional-auto only.
    assert out.marking_gate.consequential is True
    assert out.marking_gate.final is False
    assert is_provisional_auto(out.marking_gate) is True


def test_consequential_mark_is_final_only_after_human_confirmation():
    eng = EvaluationEngine(second_model=_AgreeingSecondModel())
    out = eng.post_submission(_objective_submission("10/2", 5.0))
    gate = out.marking_gate
    assert gate.final is False
    confirmed = confirm_mark(gate, confirmed_by=uuid4(), adjusted_score=0.9)
    assert confirmed.human_confirmed is True
    assert confirmed.final is True
    assert confirmed.effective_score == 0.9


def test_wrong_objective_answer_is_not_correct_and_flags_review():
    eng = EvaluationEngine(second_model=_AgreeingSecondModel())
    out = eng.post_submission(_objective_submission("3*4", 11.0))  # wrong
    resp = out.responses[0]
    assert resp.answer_state is not AnswerState.CORRECT
    assert resp.needs_human_review is True


def test_scanned_handwriting_poor_legibility_flags_review_never_penalises():
    eng = EvaluationEngine(second_model=_AgreeingSecondModel())
    # The objective answer is CORRECT, but the scan is barely legible.
    sub = SubmissionInput(
        submission_ref=uuid4(),
        scored_subject=uuid4(),
        responses=[
            ResponseInput(
                question_ref=uuid4(),
                expression="3*4",
                learner_answer=12.0,
                ocr_confidence=0.3,  # poor
            )
        ],
    )
    out = eng.scanned_handwriting(sub)
    resp = out.responses[0]
    # The mark is NOT reduced — the answer is still read as correct...
    assert resp.answer_state is AnswerState.CORRECT
    # ...but legibility forces review and lowers confidence below HIGH.
    assert resp.needs_human_review is True
    assert resp.confidence_band is not EvaluationConfidenceBand.HIGH
    assert resp.never_penalize_handwriting is True
    assert any("legibility" in n.lower() or "could not be read" in n.lower() for n in out.review_notes)


def test_scanned_unreadable_text_flags_review():
    eng = EvaluationEngine(second_model=_AgreeingSecondModel())
    sub = SubmissionInput(
        submission_ref=uuid4(),
        scored_subject=uuid4(),
        responses=[
            ResponseInput(
                question_ref=uuid4(),
                expression="2+2",
                learner_answer=4.0,
                ocr_text_recovered=False,
            )
        ],
    )
    out = eng.scanned_handwriting(sub)
    assert out.responses[0].needs_human_review is True


def test_preventive_is_never_consequential_or_final():
    eng = EvaluationEngine(second_model=_AgreeingSecondModel())
    out = eng.preventive_before_submission(_objective_submission("6+6", 12.0, consequential=True))
    assert out.mode is EvaluationMode.PREVENTIVE_BEFORE_SUBMISSION
    assert out.marking_gate.consequential is False
    assert out.marking_gate.final is False
    # Even confirming a preventive gate never makes it a final mark of record.
    confirmed = confirm_mark(out.marking_gate, confirmed_by=uuid4())
    assert confirmed.final is False


def test_free_text_without_provider_routes_to_review():
    eng = EvaluationEngine(second_model=_AgreeingSecondModel())
    sub = SubmissionInput(
        submission_ref=uuid4(),
        scored_subject=uuid4(),
        responses=[ResponseInput(question_ref=uuid4(), free_text="The mitochondria is the powerhouse...")],
    )
    out = eng.post_submission(sub)
    assert out.responses[0].confidence_band is EvaluationConfidenceBand.LOW
    assert out.responses[0].needs_human_review is True


def test_weakest_band_drives_submission_gate():
    eng = EvaluationEngine(second_model=_AgreeingSecondModel())
    sub = SubmissionInput(
        submission_ref=uuid4(),
        scored_subject=uuid4(),
        responses=[
            ResponseInput(question_ref=uuid4(), expression="2+2", learner_answer=4.0),  # HIGH
            ResponseInput(question_ref=uuid4(), free_text="essay"),  # LOW
        ],
    )
    out = eng.post_submission(sub)
    assert out.marking_gate.engine_confidence_band is EvaluationConfidenceBand.LOW
