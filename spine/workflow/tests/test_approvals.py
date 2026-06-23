"""Approval state-machine tests: transitions, who/when recorded, terminality."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.approvals import (
    ApprovalState,
    InMemoryApprovalLedger,
    state_clears_execution,
)
from app.models import ApprovalDecision, ApprovalDecisionKind


def _decision(rec_id, kind, *, adjustment=None):
    return ApprovalDecision(
        recommendation_id=rec_id,
        decision=kind,
        decided_by=uuid4(),
        decided_at=datetime.now(timezone.utc),
        adjustment=adjustment,
    )


def test_open_then_approve_transition():
    ledger = InMemoryApprovalLedger()
    rec_id = uuid4()
    ledger.open(rec_id)
    assert ledger.current_state(rec_id) == ApprovalState.PENDING

    rec = ledger.record_decision(_decision(rec_id, ApprovalDecisionKind.APPROVE))
    assert rec.state == ApprovalState.APPROVED
    assert ledger.is_cleared(rec_id) is True


def test_adjust_clears_execution_and_records_who_when():
    ledger = InMemoryApprovalLedger()
    rec_id = uuid4()
    ledger.open(rec_id)
    decision = _decision(rec_id, ApprovalDecisionKind.ADJUST, adjustment="reduce scope")
    rec = ledger.record_decision(decision)

    assert rec.state == ApprovalState.ADJUSTED
    assert ledger.is_cleared(rec_id) is True
    # Who/when recorded on the decision in the trail.
    assert rec.decision.decided_by == decision.decided_by
    assert rec.decision.decided_at == decision.decided_at


def test_decline_does_not_clear_execution():
    ledger = InMemoryApprovalLedger()
    rec_id = uuid4()
    ledger.open(rec_id)
    ledger.record_decision(_decision(rec_id, ApprovalDecisionKind.DECLINE))
    assert ledger.current_state(rec_id) == ApprovalState.DECLINED
    assert ledger.is_cleared(rec_id) is False


def test_decision_is_terminal_never_overwritten():
    ledger = InMemoryApprovalLedger()
    rec_id = uuid4()
    ledger.open(rec_id)
    ledger.record_decision(_decision(rec_id, ApprovalDecisionKind.APPROVE))
    with pytest.raises(ValueError):
        ledger.record_decision(_decision(rec_id, ApprovalDecisionKind.DECLINE))


def test_decision_on_unopened_recommendation_refused():
    ledger = InMemoryApprovalLedger()
    with pytest.raises(ValueError):
        ledger.record_decision(_decision(uuid4(), ApprovalDecisionKind.APPROVE))


def test_reopen_refused():
    ledger = InMemoryApprovalLedger()
    rec_id = uuid4()
    ledger.open(rec_id)
    with pytest.raises(ValueError):
        ledger.open(rec_id)


def test_adjust_without_adjustment_is_rejected_by_model():
    with pytest.raises(Exception):
        _decision(uuid4(), ApprovalDecisionKind.ADJUST)  # no adjustment


def test_trail_is_ordered_and_complete():
    ledger = InMemoryApprovalLedger()
    rec_id = uuid4()
    ledger.open(rec_id)
    ledger.record_decision(_decision(rec_id, ApprovalDecisionKind.APPROVE))
    trail = ledger.trail(rec_id)
    assert [r.state for r in trail] == [ApprovalState.PENDING, ApprovalState.APPROVED]


def test_state_clears_execution_helper():
    assert state_clears_execution(ApprovalState.APPROVED) is True
    assert state_clears_execution(ApprovalState.ADJUSTED) is True
    assert state_clears_execution(ApprovalState.DECLINED) is False
    assert state_clears_execution(ApprovalState.PENDING) is False
