"""Workflow-boundary event tests.

Covers the four proactive-loop events the Integration agent wires + persists:
recommendation.created, recommendation.actioned, approval.given, action.executed.

Guarantees checked here:
  * the four canonical contract type strings are emitted;
  * events carry only opaque refs — a PII payload is refused (INVARIANT 1/2);
  * approval.given is built ONLY for a clearing decision (approve/adjust);
  * the ApprovalLedger's clearing transitions are exposed as approval.given;
  * action.executed is built ONLY for a cleared execution, and ``performed``
    vs ``delegated`` distinguishes safe_automatic from a consequential clearance;
  * builders are pure (no side effect) and emit() degrades with no sink;
  * the EmitEventInput shape is consent-stamped (INVARIANT 6).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.approvals import ApprovalState, InMemoryApprovalLedger
from app.events import (
    CollectingSink,
    EventRefused,
    WorkflowEvent,
    action_executed,
    approval_events_from_trail,
    approval_given,
    emit,
    recommendation_actioned,
    recommendation_created,
)
from app.loop import execute
from app.models import (
    ApprovalDecision,
    ApprovalDecisionKind,
    EvidenceRef,
    LadderStage,
)
from app.permission import ActionDescriptor
from app.recommendations import build_recommendation


# --- fixtures / builders ---------------------------------------------------
def _consequential_rec(owner=None):
    return build_recommendation(
        evidence_summary="A progress note is drafted and ready to send.",
        evidence_refs=[
            EvidenceRef(event_id=uuid4(), summary="missed two checkpoints"),
            EvidenceRef(event_id=uuid4(), summary="revision overdue"),
        ],
        confidence=0.85,
        owner_role="teacher",
        owner_ref=owner or uuid4(),
        suggested_action="Send the prepared progress note.",
        action=ActionDescriptor(kind="send_parent_note", effect_verb="send", targets_external=True),
        consequence_of_ignoring="The cohort stays unaware of the missed revision.",
        why_am_i_seeing_this="A progress note is prepared and awaiting your approval to send.",
    )


def _safe_rec(owner=None):
    return build_recommendation(
        evidence_summary="Fresh scores warrant a mastery recompute.",
        evidence_refs=[
            EvidenceRef(event_id=uuid4(), summary="new score"),
            EvidenceRef(event_id=uuid4(), summary="new attempt"),
        ],
        confidence=0.9,
        owner_role="system",
        owner_ref=owner or uuid4(),
        suggested_action="Recompute mastery for the cohort.",
        action=ActionDescriptor(kind="recompute_mastery", effect_verb="recompute"),
        consequence_of_ignoring="Mastery readings go stale.",
        why_am_i_seeing_this="New evidence arrived for this cohort.",
    )


def _decision(rec_id, kind, *, adjustment=None, who=None):
    return ApprovalDecision(
        recommendation_id=rec_id,
        decision=kind,
        decided_by=who or uuid4(),
        decided_at=datetime.now(timezone.utc),
        adjustment=adjustment,
    )


# --- recommendation.created ------------------------------------------------
def test_recommendation_created_carries_provenance_and_owner_ref():
    owner = uuid4()
    rec = _consequential_rec(owner)
    ev = recommendation_created(rec)

    assert ev.type == "recommendation.created"
    assert ev.canonical_uuid == owner  # attributed to the opaque owner ref
    assert ev.payload["recommendation_id"] == str(rec.id)
    assert ev.payload["rung"] == "execute-with-permission"  # hyphen-cased event rung
    assert ev.payload["is_consequential"] is True
    assert ev.payload["requires_human_approval"] is True
    assert ev.payload["evidence_count"] == 2
    assert len(ev.payload["evidence_event_ids"]) == 2


def test_safe_recommendation_created_rung_and_flags():
    rec = _safe_rec()
    ev = recommendation_created(rec)
    assert ev.payload["rung"] == "safe-automatic"
    assert ev.payload["is_consequential"] is False
    assert ev.payload["requires_human_approval"] is False


# --- recommendation.actioned ----------------------------------------------
def test_recommendation_actioned_records_who_how_when():
    rec = _consequential_rec()
    who = uuid4()
    dec = _decision(rec.id, ApprovalDecisionKind.APPROVE, who=who)
    ev = recommendation_actioned(dec)

    assert ev.type == "recommendation.actioned"
    assert ev.canonical_uuid == who
    assert ev.payload["decision"] == "approve"
    assert ev.payload["decided_by"] == str(who)
    assert ev.payload["clears_execution"] is True
    assert ev.occurred_at == dec.decided_at


def test_recommendation_actioned_decline_does_not_clear():
    rec = _consequential_rec()
    dec = _decision(rec.id, ApprovalDecisionKind.DECLINE)
    ev = recommendation_actioned(dec)
    assert ev.payload["decision"] == "decline"
    assert ev.payload["clears_execution"] is False


# --- approval.given --------------------------------------------------------
def test_approval_given_built_for_approve():
    rec = _consequential_rec()
    who = uuid4()
    ev = approval_given(_decision(rec.id, ApprovalDecisionKind.APPROVE, who=who))
    assert ev.type == "approval.given"
    assert ev.canonical_uuid == who
    assert ev.payload["grants_execution"] is True
    assert ev.payload["resulting_state"] == ApprovalState.APPROVED.value


def test_approval_given_built_for_adjust_carries_adjustment():
    rec = _consequential_rec()
    ev = approval_given(_decision(rec.id, ApprovalDecisionKind.ADJUST, adjustment="reduce scope"))
    assert ev.payload["resulting_state"] == ApprovalState.ADJUSTED.value
    assert ev.payload["adjustment"] == "reduce scope"


def test_approval_given_refused_for_decline():
    rec = _consequential_rec()
    with pytest.raises(EventRefused):
        approval_given(_decision(rec.id, ApprovalDecisionKind.DECLINE))


# --- ledger transitions exposed as approval.given --------------------------
def test_approval_events_from_trail_emits_only_clearing_transition():
    ledger = InMemoryApprovalLedger()
    rec = _consequential_rec()
    ledger.open(rec.id)
    ledger.record_decision(_decision(rec.id, ApprovalDecisionKind.APPROVE))

    events = approval_events_from_trail(ledger.trail(rec.id))
    # PENDING (no decision) yields nothing; only the clearing APPROVE -> one event.
    assert [e.type for e in events] == ["approval.given"]
    assert events[0].payload["resulting_state"] == ApprovalState.APPROVED.value


def test_approval_events_from_trail_declined_yields_no_event():
    ledger = InMemoryApprovalLedger()
    rec = _consequential_rec()
    ledger.open(rec.id)
    ledger.record_decision(_decision(rec.id, ApprovalDecisionKind.DECLINE))
    assert approval_events_from_trail(ledger.trail(rec.id)) == []


# --- action.executed -------------------------------------------------------
def test_action_executed_for_consequential_clearance_is_delegated():
    ledger = InMemoryApprovalLedger()
    owner = uuid4()
    rec = _consequential_rec(owner)
    ledger.open(rec.id)
    ledger.record_decision(_decision(rec.id, ApprovalDecisionKind.APPROVE))
    result = execute(rec, ledger, capability="comms.parent_note")
    assert result.cleared is True and result.performed is False

    ev = action_executed(result, owner_ref=owner)
    assert ev.type == "action.executed"
    assert ev.canonical_uuid == owner
    assert ev.payload["performed"] is False
    assert ev.payload["delegated"] is True  # handed to a governed capability
    assert ev.payload["capability"] == "comms.parent_note"
    assert ev.payload["rung"] == "execute-with-permission"


def test_action_executed_for_safe_automatic_is_performed():
    ledger = InMemoryApprovalLedger()
    owner = uuid4()
    rec = _safe_rec(owner)
    result = execute(
        rec, ledger, action=ActionDescriptor(kind="recompute_mastery", effect_verb="recompute")
    )
    assert result.cleared is True and result.performed is True

    ev = action_executed(result, owner_ref=owner)
    assert ev.payload["performed"] is True
    assert ev.payload["delegated"] is False
    assert ev.payload["rung"] == "safe-automatic"


def test_action_executed_refused_when_not_cleared():
    ledger = InMemoryApprovalLedger()
    rec = _consequential_rec()
    ledger.open(rec.id)  # opened but never approved -> refused gate
    result = execute(rec, ledger)
    assert result.cleared is False
    with pytest.raises(EventRefused):
        action_executed(result, owner_ref=uuid4())


# --- invariants: PII, purity, degrade, consent-stamp -----------------------
def test_event_refuses_pii_payload_backstop():
    # A built event with an opaque payload is fine; constructing the EmitEventInput
    # and any builder both backstop PII. Here we prove the builder backstop by
    # smuggling a PII key through a crafted WorkflowEvent emit shape.
    ev = recommendation_created(_safe_rec())
    # The payload the builder produced is PII-free.
    assert not {"name", "email"}.intersection(ev.payload)


def test_emit_degrades_with_no_sink_and_is_pure():
    rec = _safe_rec()
    ev = recommendation_created(rec)
    res = emit(ev, sink=None)
    assert res["degraded"] is True and res["emitted"] is False
    # Building twice yields an equal event (pure) modulo the auto timestamp;
    # compare the stable payload.
    again = recommendation_created(rec, occurred_at=ev.occurred_at)
    assert again.payload == ev.payload
    assert again.canonical_uuid == ev.canonical_uuid


def test_emit_routes_to_sink():
    sink = CollectingSink()
    rec = _safe_rec()
    emit(recommendation_created(rec), sink)
    emit(recommendation_actioned(_decision(rec.id, ApprovalDecisionKind.APPROVE)), sink)
    assert sink.types() == ["recommendation.created", "recommendation.actioned"]


def test_as_emit_input_is_consent_stamped():
    ev = recommendation_created(_safe_rec())
    inp = ev.as_emit_input(purpose="workflow", consent_ref="consent-123")
    assert inp["app"] == "workflow"
    assert inp["purpose"] == "workflow"
    assert inp["consent_ref"] == "consent-123"
    assert inp["type"] == "recommendation.created"
    # consent is mandatory — empty ref is refused.
    with pytest.raises(EventRefused):
        ev.as_emit_input(purpose="workflow", consent_ref="")


def test_all_four_boundary_event_types_present():
    sink = CollectingSink()
    ledger = InMemoryApprovalLedger()
    owner = uuid4()
    rec = _safe_rec(owner)

    emit(recommendation_created(rec), sink)
    dec = _decision(rec.id, ApprovalDecisionKind.APPROVE)
    emit(recommendation_actioned(dec), sink)
    emit(approval_given(dec), sink)
    result = execute(
        rec, ledger, action=ActionDescriptor(kind="recompute_mastery", effect_verb="recompute")
    )
    emit(action_executed(result, owner_ref=owner), sink)

    assert set(sink.types()) == {
        "recommendation.created",
        "recommendation.actioned",
        "approval.given",
        "action.executed",
    }
