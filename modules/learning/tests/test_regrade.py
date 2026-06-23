"""The 'I think I am right' re-grade path + confidence check-ins + reflection (d11/d12)."""

from __future__ import annotations

from learning import regrade
from learning.regrade import (
    Calibration,
    Confidence,
    RegradeDispute,
    RegradeOutcome,
    RegradeRoute,
    assess_calibration,
    prepare_regrade,
    reflection_prompt,
)


# --- confidence check-ins / calibration ------------------------------------
def test_confident_wrong_is_overconfident():
    c = assess_calibration(confidence=Confidence.CERTAIN, correct=False)
    assert c.calibration is Calibration.OVERCONFIDENT


def test_unsure_right_is_underconfident():
    c = assess_calibration(confidence=Confidence.UNSURE, correct=True)
    assert c.calibration is Calibration.UNDERCONFIDENT


def test_confident_right_is_well_calibrated():
    c = assess_calibration(confidence=Confidence.CERTAIN, correct=True)
    assert c.calibration is Calibration.WELL_CALIBRATED


def test_guessed_right_flagged_distinctly():
    c = assess_calibration(confidence=Confidence.GUESSING, correct=True)
    assert c.calibration is Calibration.GUESSED_RIGHT


def test_check_in_plain_language_no_percentage():
    c = assess_calibration(confidence=Confidence.CERTAIN, correct=False)
    assert "%" not in c.plain_language


# --- reflection prompts ----------------------------------------------------
def test_reflection_prompt_is_always_a_question():
    for conf in Confidence:
        for correct in (True, False):
            c = assess_calibration(confidence=conf, correct=correct)
            assert "?" in reflection_prompt(c)


def test_reflection_prompt_fits_calibration():
    over = assess_calibration(confidence=Confidence.CERTAIN, correct=False)
    under = assess_calibration(confidence=Confidence.UNSURE, correct=True)
    assert reflection_prompt(over) != reflection_prompt(under)


# --- the re-grade / dispute path -------------------------------------------
def test_objective_dispute_vindicates_learner_but_requires_approval():
    d = RegradeDispute(
        topic_id="t", question_id="q1", learner_answer="4",
        original_marked_correct=False, learner_reasoning="8 times a half is 4.",
        deterministic_check={"expression": "8 * 0.5", "claimed_answer": 4.0},
        is_consequential=True,
    )
    req = prepare_regrade(d)
    assert req.route is RegradeRoute.AUTO_VERIFY
    assert req.advisory_outcome is RegradeOutcome.LEARNER_VINDICATED
    # Never auto-overturned: a consequential mark needs a human (PERMISSION LADDER).
    assert req.requires_approval is True
    assert req.auto_overturned is False


def test_objective_dispute_can_uphold_original():
    d = RegradeDispute(
        topic_id="t", question_id="q1", learner_answer="8",
        original_marked_correct=False, learner_reasoning="I think it is 8.",
        deterministic_check={"expression": "8 * 0.5", "claimed_answer": 4.0},
    )
    req = prepare_regrade(d)
    assert req.advisory_outcome is RegradeOutcome.ORIGINAL_UPHELD


def test_subjective_dispute_routes_to_human():
    d = RegradeDispute(
        topic_id="t", question_id="q2", learner_answer="my essay argument",
        original_marked_correct=False, learner_reasoning="My thesis was clear.",
        deterministic_check=None,
    )
    req = prepare_regrade(d)
    assert req.route is RegradeRoute.HUMAN_REVIEW
    assert req.advisory_outcome is RegradeOutcome.INCONCLUSIVE
    assert req.requires_approval is True


def test_request_carries_explainable_provenance_and_reasoning():
    d = RegradeDispute(
        topic_id="t", question_id="q1", learner_answer="4",
        original_marked_correct=False, learner_reasoning="halving 8 gives 4",
        deterministic_check={"claimed_answer": 4.0},
    )
    req = prepare_regrade(d)
    assert req.provenance and req.learner_reasoning == "halving 8 gives 4"
    assert req.prepared_at  # timestamped


def test_non_consequential_dispute_does_not_require_approval():
    d = RegradeDispute(
        topic_id="t", question_id="q3", learner_answer="4",
        original_marked_correct=False, learner_reasoning="practice item",
        deterministic_check={"claimed_answer": 4.0}, is_consequential=False,
    )
    req = prepare_regrade(d)
    assert req.requires_approval is False
    assert req.auto_overturned is False  # still never auto-applies a change
