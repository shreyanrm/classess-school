"""Preventive feedback — graduated hints, re-grade, confidence/reflection (B6 d11).

Pins the non-negotiables:
  - the graduated-hint ladder NEVER reveals the final answer and is never forced,
  - hints are pulled one rung at a time and stop at check-your-working,
  - an "I think I'm right" re-grade is human-final and changes no mark,
  - a confidence check-in / reflection prompt is a signal, never a mark.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.contracts import AnswerState, EvaluationConfidenceBand
from app.feedback import (
    MAX_HINT_TIER,
    ConfidenceCheckIn,
    GraduatedHint,
    HintTier,
    RegradeRequest,
    StatedConfidence,
    confidence_check_in,
    reflection_prompt,
    request_regrade,
    start_hint_ladder,
)


# --- graduated-hint ladder -------------------------------------------------
def test_hint_ladder_pulls_one_rung_at_a_time_in_order():
    ladder = start_hint_ladder(response_ref=uuid4(), answer_state=AnswerState.INCOMPLETE)
    assert ladder.pulled == 0

    seen_tiers = []
    while not ladder.exhausted:
        ladder, hint = ladder.next_hint()
        assert hint is not None
        seen_tiers.append(hint.tier)
    # Escalates exactly orient -> strategy -> next_step -> check_working.
    assert seen_tiers == [HintTier.ORIENT, HintTier.STRATEGY, HintTier.NEXT_STEP, HintTier.CHECK_WORKING]


def test_hint_ladder_never_reveals_the_answer_and_stops_at_check_working():
    ladder = start_hint_ladder(response_ref=uuid4())
    last_hint = None
    while not ladder.exhausted:
        ladder, hint = ladder.next_hint()
        assert hint.reveals_answer is False
        last_hint = hint
    # Exhausted -> no further hint; the ladder never hands over the answer.
    assert ladder.exhausted is True
    assert ladder.reveals_answer is False
    assert last_hint.tier is MAX_HINT_TIER
    advanced, beyond = ladder.next_hint()
    assert beyond is None
    assert advanced is ladder  # unchanged once exhausted


def test_hint_is_structurally_forbidden_from_revealing_the_answer():
    with pytest.raises(ValueError):
        GraduatedHint(tier=HintTier.NEXT_STEP, text="The answer is 42.", reveals_answer=True)


def test_hint_ladder_is_not_forced_learner_can_stop_early():
    ladder = start_hint_ladder(response_ref=uuid4())
    ladder, _first = ladder.next_hint()
    # Learner takes one hint and stops — pulled count reflects the choice.
    assert ladder.pulled == 1
    assert ladder.exhausted is False
    assert ladder.rung == "recommend"


def test_strategy_hint_leans_to_response_type_without_revealing():
    misund = start_hint_ladder(response_ref=uuid4(), answer_state=AnswerState.MISUNDERSTOOD)
    misund, _ = misund.next_hint()  # orient
    misund, strat = misund.next_hint()  # strategy
    assert strat.tier is HintTier.STRATEGY
    assert "idea" in strat.text.lower() or "rule" in strat.text.lower()
    assert strat.reveals_answer is False


# --- "I think I'm right" re-grade ------------------------------------------
def test_regrade_request_is_human_final_and_changes_no_mark():
    req = request_regrade(
        submission_ref=uuid4(),
        question_ref=uuid4(),
        requested_by=uuid4(),
        engine_answer_state=AnswerState.INCOMPLETE,
        engine_confidence_band=EvaluationConfidenceBand.MIDDLE,
        learner_reason="I used a different valid method.",
    )
    assert isinstance(req, RegradeRequest)
    assert req.requires_approval is True
    assert req.rung == "recommend"
    assert "changes no mark" in req.rationale.lower()


def test_regrade_on_low_confidence_band_flags_a_human_look_is_warranted():
    req = request_regrade(
        submission_ref=uuid4(),
        question_ref=uuid4(),
        requested_by=uuid4(),
        engine_answer_state=AnswerState.MISUNDERSTOOD,
        engine_confidence_band=EvaluationConfidenceBand.LOW,
    )
    assert "not fully confident" in req.rationale.lower()


# --- confidence check-in + reflection --------------------------------------
def test_confidence_check_in_flags_overconfidence_as_signal_not_penalty():
    ci = confidence_check_in(
        response_ref=uuid4(),
        stated=StatedConfidence.CONFIDENT,
        engine_band=EvaluationConfidenceBand.LOW,
    )
    assert isinstance(ci, ConfidenceCheckIn)
    assert ci.miscalibrated is True
    assert "no penalty" in ci.rationale.lower()
    assert ci.rung == "recommend"


def test_confidence_check_in_well_calibrated_when_aligned():
    ci = confidence_check_in(
        response_ref=uuid4(),
        stated=StatedConfidence.CONFIDENT,
        engine_band=EvaluationConfidenceBand.HIGH,
    )
    assert ci.miscalibrated is False
    assert ci.calibration_gap < 0.4


def test_confidence_check_in_underconfidence_is_named():
    ci = confidence_check_in(
        response_ref=uuid4(),
        stated=StatedConfidence.NOT_SURE,
        engine_band=EvaluationConfidenceBand.HIGH,
    )
    assert ci.miscalibrated is True
    assert "stronger" in ci.rationale.lower() or "more" in ci.rationale.lower()


def test_reflection_prompt_is_shaped_by_answer_state_and_is_not_graded():
    for state in (AnswerState.CORRECT, AnswerState.INCOMPLETE, AnswerState.MISUNDERSTOOD):
        rp = reflection_prompt(response_ref=uuid4(), answer_state=state)
        assert rp.answer_state is state
        assert rp.prompt
        assert rp.rung == "recommend"
    # The misunderstood prompt invites revisiting the idea, gently.
    rp = reflection_prompt(response_ref=uuid4(), answer_state=AnswerState.MISUNDERSTOOD)
    assert "idea" in rp.prompt.lower()
