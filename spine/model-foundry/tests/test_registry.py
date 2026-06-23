"""Registry: permission-laddered promotion — requires approval, never auto-fires."""

from __future__ import annotations

import pytest

from app.eval import Comparison, Scorecard
from app.registry import (
    CandidateState,
    ModelRegistry,
    PromotionNotApproved,
)

from .conftest import APPROVER


def _card(model="cand", composite_axes=0.9, refusal=1.0, verify=0.9):
    return Scorecard(
        model_label=model,
        dataset_id="ds-1",
        held_out_n=10,
        overall_accuracy=composite_axes,
        per_class_accuracy={},
        mastery_agreement=composite_axes,
        gap_classification_accuracy=composite_axes,
        generate_verify_pass_rate=verify,
        refusal_correctness=refusal,
    )


def _better_comparison():
    cand = _card("cand", 0.9)
    inc = _card("inc", 0.5)
    return Comparison(candidate=cand, incumbent=inc, candidate_better=True, deltas={"composite": 0.4}, summary="candidate better")


def _worse_comparison():
    cand = _card("cand", 0.5)
    inc = _card("inc", 0.9)
    return Comparison(candidate=cand, incumbent=inc, candidate_better=False, deltas={"composite": -0.4}, summary="candidate NOT better: no composite gain")


def _registered(reg: ModelRegistry, cid="cand-1"):
    reg.register(candidate_id=cid, student_label="edge-v1", dataset_id="ds-1", dataset_content_hash="abc")
    return cid


def test_request_always_requires_approval():
    reg = ModelRegistry()
    cid = _registered(reg)
    reg.attach_eval(candidate_id=cid, scorecard=_card(), comparison=_better_comparison())
    decision = reg.request_promotion(candidate_id=cid)
    assert decision.requires_approval is True
    assert decision.rung == "execute-with-permission"
    assert decision.eligible is True
    # request does NOT promote
    assert reg.active_track2() is None
    assert reg.get(cid).state is CandidateState.PROMOTION_REQUESTED


def test_request_without_eval_not_eligible():
    reg = ModelRegistry()
    cid = _registered(reg)
    decision = reg.request_promotion(candidate_id=cid)
    assert decision.requires_approval is True
    assert decision.eligible is False
    assert reg.active_track2() is None


def test_request_when_not_better_not_eligible():
    reg = ModelRegistry()
    cid = _registered(reg)
    reg.attach_eval(candidate_id=cid, scorecard=_card(), comparison=_worse_comparison())
    decision = reg.request_promotion(candidate_id=cid)
    assert decision.eligible is False
    assert reg.active_track2() is None


def test_cannot_promote_without_request():
    reg = ModelRegistry()
    cid = _registered(reg)
    reg.attach_eval(candidate_id=cid, scorecard=_card(), comparison=_better_comparison())
    # Skip request -> approve directly must fail.
    with pytest.raises(PromotionNotApproved):
        reg.approve_promotion(candidate_id=cid, approved_by=APPROVER)


def test_approved_promotion_advances_and_is_immutable():
    reg = ModelRegistry()
    cid = _registered(reg)
    reg.attach_eval(candidate_id=cid, scorecard=_card(), comparison=_better_comparison())
    reg.request_promotion(candidate_id=cid)
    record = reg.approve_promotion(candidate_id=cid, approved_by=APPROVER)
    assert reg.active_track2() == cid
    assert reg.get(cid).state is CandidateState.PROMOTED
    assert record.approved_by == APPROVER
    assert record.previous_active is None
    # history is append-only
    assert reg.history() == (record,)


def test_promotion_history_records_succession():
    reg = ModelRegistry()
    for cid in ("cand-1", "cand-2"):
        reg.register(candidate_id=cid, student_label="edge", dataset_id="ds", dataset_content_hash="h")
        reg.attach_eval(candidate_id=cid, scorecard=_card(), comparison=_better_comparison())
        reg.request_promotion(candidate_id=cid)
        reg.approve_promotion(candidate_id=cid, approved_by=APPROVER)
    hist = reg.history()
    assert len(hist) == 2
    assert hist[1].previous_active == "cand-1"
    assert reg.active_track2() == "cand-2"


def test_only_track2_candidates_registered():
    reg = ModelRegistry()
    with pytest.raises(ValueError):
        reg.register(candidate_id="x", student_label="y", dataset_id="d", dataset_content_hash="h", track=1)
