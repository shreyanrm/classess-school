"""The four named build-interaction types: contract + verification (d12)."""

from __future__ import annotations

import pytest

from learning import interactions
from learning.interactions import (
    ALL_INTERACTION_TYPES,
    AssembleTheProof,
    DerivationSlot,
    FillTheMissingStep,
    InteractionType,
    KeyPoint,
    PredictThenCheck,
    ProofStep,
    TeachItBack,
    build_interaction_evidence,
)


def test_all_four_interaction_types_present():
    assert set(ALL_INTERACTION_TYPES) == {
        InteractionType.PREDICT_THEN_CHECK,
        InteractionType.ASSEMBLE_THE_PROOF,
        InteractionType.FILL_THE_MISSING_STEP,
        InteractionType.TEACH_IT_BACK,
    }


# --- 1 · predict-then-check ------------------------------------------------
def test_predict_then_check_requires_prediction_before_check():
    sim = PredictThenCheck(topic_id="t", prompt="8 times one half?", check_expression="8 * 0.5", actual_outcome=4.0)
    with pytest.raises(RuntimeError):
        sim.check()  # no prediction committed yet


def test_predict_then_check_rejects_prediction_after_check():
    sim = PredictThenCheck(topic_id="t", prompt="p", check_expression="8 * 0.5", actual_outcome=4.0)
    sim.commit_prediction(4.0)
    sim.check()
    with pytest.raises(RuntimeError):
        sim.commit_prediction(4.0)  # too late — must commit first


def test_predict_then_check_surfaces_the_gap():
    sim = PredictThenCheck(topic_id="t", prompt="p", check_expression="8 * 0.5", actual_outcome=4.0)
    sim.commit_prediction(8.0)  # the "multiplication always increases" prediction
    v = sim.check()
    assert v.correct is False
    assert v.detail["predicted"] == 8.0 and v.detail["actual"] == 4.0
    assert "?" in v.feedback  # posed, not a correction


def test_predict_then_check_correct_prediction_passes():
    sim = PredictThenCheck(topic_id="t", prompt="p", check_expression="2 + 2", actual_outcome=4.0)
    sim.commit_prediction(4.0)
    v = sim.check()
    assert v.correct and v.score == 1.0


# --- 2 · assemble-the-proof ------------------------------------------------
def _proof():
    return AssembleTheProof(
        topic_id="t", prompt="assemble it",
        steps=(
            ProofStep("s1", "from given A derive B", requires=("A",), establishes="B"),
            ProofStep("s2", "from B derive C", requires=("B",), establishes="C"),
            ProofStep("s3", "from C derive goal", requires=("C",), establishes="GOAL"),
        ),
        goal="GOAL", givens=("A",),
    )


def test_assemble_the_proof_valid_order_passes():
    v = _proof().verify(["s1", "s2", "s3"])
    assert v.correct and v.score == 1.0 and v.detail["reached_goal"]


def test_assemble_the_proof_premise_before_established_fails():
    # s2 needs B which s1 establishes; placing s2 first must fail structurally.
    v = _proof().verify(["s2", "s1", "s3"])
    assert v.correct is False
    assert v.detail["first_unmet_step"] == "s2"
    assert "?" in v.feedback


def test_assemble_the_proof_incomplete_chain_not_correct():
    v = _proof().verify(["s1", "s2"])  # never reaches GOAL
    assert v.correct is False
    assert v.detail["reached_goal"] is False


# --- 3 · fill-the-missing-step ---------------------------------------------
def _fill():
    return FillTheMissingStep(
        topic_id="t", prompt="fill it",
        visible_steps=("2x + 4 = 10", "____", "x = 3"),
        slots=(DerivationSlot("gap1", "2x = 6", acceptable=("2x=6",)),),
    )


def test_fill_correct_slot_passes():
    v = _fill().verify({"gap1": "2x = 6"})
    assert v.correct and v.score == 1.0


def test_fill_accepts_equivalent_form():
    v = _fill().verify({"gap1": "2X=6"})  # normalised: case + spaces ignored
    assert v.correct


def test_fill_wrong_slot_is_posed_not_lectured():
    v = _fill().verify({"gap1": "x = 6"})
    assert v.correct is False
    assert "gap1" in v.detail["unsolved"]
    assert "?" in v.feedback


def test_fill_missing_slot_counts_as_unsolved():
    v = _fill().verify({})
    assert v.correct is False and "gap1" in v.detail["unsolved"]


# --- 4 · teach-it-back -----------------------------------------------------
def _teach():
    return TeachItBack(
        topic_id="t", prompt="teach me fractions adding",
        key_points=(
            KeyPoint("common", "how you make the denominators match", ("common denominator", "same denominator")),
            KeyPoint("numerator", "what happens to the numerators", ("add the numerators", "add the tops")),
        ),
        pass_threshold=0.7,
    )


def test_teach_back_full_coverage_passes():
    v = _teach().verify("First you find a common denominator, then you add the numerators.")
    assert v.correct and v.score == 1.0
    assert v.detail["missing"] == ()


def test_teach_back_gap_becomes_a_posed_followup():
    v = _teach().verify("You add the tops together.")  # misses the common denominator
    assert v.correct is False
    assert "common" in v.detail["missing"]
    assert "?" in v.feedback  # the companion asks, never corrects
    assert "forgot" not in v.feedback.lower()


def test_teach_back_follow_up_none_when_full():
    t = _teach()
    assert t.follow_up("Find a common denominator, then add the numerators.") is None


# --- shared evidence contract ---------------------------------------------
def test_interaction_evidence_independent_when_no_help():
    sim = PredictThenCheck(topic_id="t", prompt="p", check_expression="2+2", actual_outcome=4.0)
    sim.commit_prediction(4.0)
    v = sim.check()
    payload = build_interaction_evidence(
        interaction=InteractionType.PREDICT_THEN_CHECK, topic_id="t",
        verdict=v, used_help=False, time_taken_ms=20_000,
    )
    assert payload["assistance_level"] == "Independent"
    assert payload["mode"] == "independent"
    assert payload["correct"] is True


def test_interaction_evidence_supported_when_help_used():
    v = _proof().verify(["s1", "s2", "s3"])
    payload = build_interaction_evidence(
        interaction=InteractionType.ASSEMBLE_THE_PROOF, topic_id="t",
        verdict=v, used_help=True, time_taken_ms=30_000,
    )
    assert payload["assistance_level"] == "Hint"
    assert payload["mode"] == "supported"  # a revealed build is SUPPORTED evidence
