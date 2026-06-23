"""End-to-end loop tests: a consequential action never auto-fires; the gate
clears only after human approval; safe_automatic proceeds; the seven steps
compose; PII is refused at observe; single-evidence judgments are dropped.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.approvals import InMemoryApprovalLedger
from app.loop import (
    InterpretedSignal,
    ObservedEvent,
    WorkflowCycle,
    execute,
    interpret,
    learn,
    observe,
    outcome,
)
from app.models import (
    ApprovalDecision,
    ApprovalDecisionKind,
    EvidenceRef,
    LadderStage,
)
from app.permission import ActionDescriptor
from app.recommendations import (
    CohortWeaknessSignal,
    build_cohort_weakness_recommendation,
    build_recommendation,
)


def _consequential_rec():
    return build_recommendation(
        evidence_summary="A parent message is drafted and ready to send.",
        evidence_refs=[EvidenceRef(event_id=uuid4(), summary="missed two checkpoints"),
                       EvidenceRef(event_id=uuid4(), summary="revision overdue")],
        confidence=0.85,
        owner_role="teacher",
        owner_ref=uuid4(),
        suggested_action="Send the prepared progress note to the parent.",
        action=ActionDescriptor(kind="send_parent_note", effect_verb="send", targets_external=True),
        consequence_of_ignoring="The parent stays unaware of the missed revision.",
        why_am_i_seeing_this="A progress note is prepared and awaiting your approval to send.",
    )


def test_consequential_action_never_autofires_without_approval():
    ledger = InMemoryApprovalLedger()
    rec = _consequential_rec()
    assert rec.is_consequential is True
    assert rec.ladder_stage == LadderStage.EXECUTE_WITH_PERMISSION.value

    ledger.open(rec.id)
    result = execute(rec, ledger,
                     action=ActionDescriptor(kind="send_parent_note", effect_verb="send"))
    assert result.cleared is False
    assert result.performed is False


def test_consequential_action_clears_only_after_human_approval():
    ledger = InMemoryApprovalLedger()
    rec = _consequential_rec()
    ledger.open(rec.id)
    ledger.record_decision(ApprovalDecision(
        recommendation_id=rec.id,
        decision=ApprovalDecisionKind.APPROVE,
        decided_by=uuid4(),
        decided_at=datetime.now(timezone.utc),
    ))
    result = execute(rec, ledger, capability="comms.parent_note")
    assert result.cleared is True
    # Cleared, but the package itself performs nothing — delegated to a capability.
    assert result.performed is False
    assert result.capability == "comms.parent_note"


def test_declined_consequential_action_stays_refused():
    ledger = InMemoryApprovalLedger()
    rec = _consequential_rec()
    ledger.open(rec.id)
    ledger.record_decision(ApprovalDecision(
        recommendation_id=rec.id,
        decision=ApprovalDecisionKind.DECLINE,
        decided_by=uuid4(),
        decided_at=datetime.now(timezone.utc),
    ))
    result = execute(rec, ledger)
    assert result.cleared is False


def test_safe_automatic_proceeds_unattended():
    ledger = InMemoryApprovalLedger()
    rec = build_recommendation(
        evidence_summary="Fresh scores warrant a mastery recompute.",
        evidence_refs=[EvidenceRef(event_id=uuid4(), summary="new score"),
                       EvidenceRef(event_id=uuid4(), summary="new attempt")],
        confidence=0.9,
        owner_role="system",
        owner_ref=uuid4(),
        suggested_action="Recompute mastery for the cohort.",
        action=ActionDescriptor(kind="recompute_mastery", effect_verb="recompute"),
        consequence_of_ignoring="Mastery readings go stale.",
        why_am_i_seeing_this="New evidence arrived for this cohort.",
    )
    assert rec.is_consequential is False
    assert rec.ladder_stage == LadderStage.SAFE_AUTOMATIC.value
    result = execute(rec, ledger,
                     action=ActionDescriptor(kind="recompute_mastery", effect_verb="recompute"))
    assert result.cleared is True
    assert result.performed is True


def test_reclassification_mismatch_fails_closed():
    # A recommendation claims safe_automatic but the action is actually a send.
    ledger = InMemoryApprovalLedger()
    rec = build_recommendation(
        evidence_summary="s",
        evidence_refs=[EvidenceRef(event_id=uuid4(), summary="a"),
                       EvidenceRef(event_id=uuid4(), summary="b")],
        confidence=0.9,
        owner_role="system",
        owner_ref=uuid4(),
        suggested_action="recompute",
        action=ActionDescriptor(kind="recompute_mastery", effect_verb="recompute"),
        consequence_of_ignoring="y",
        why_am_i_seeing_this="z",
    )
    # Now pass a consequential action at execute time — defence in depth refuses.
    result = execute(rec, ledger,
                     action=ActionDescriptor(kind="recompute_mastery", effect_verb="send"))
    assert result.cleared is False


def test_observe_refuses_pii():
    with pytest.raises(ValueError):
        observe([ObservedEvent(event_id=uuid4(), canonical_uuid=uuid4(),
                               type="attempt.recorded", payload={"email": "x@y.z"})])


def test_interpret_drops_single_evidence_judgments():
    def interp(_events):
        return [InterpretedSignal(kind="cohort_weakness", summary="weak",
                                  confidence=0.9, evidence_event_ids=[uuid4()])]
    signals = interpret([], [interp], require_corroboration=True)
    assert signals == []
    # And keeps a corroborated one.
    def interp2(_events):
        return [InterpretedSignal(kind="cohort_weakness", summary="weak",
                                  confidence=0.9, evidence_event_ids=[uuid4(), uuid4()])]
    assert len(interpret([], [interp2], require_corroboration=True)) == 1


def test_full_cycle_composes_and_gates():
    ledger = InMemoryApprovalLedger()
    owner = uuid4()
    ev_ids = [uuid4(), uuid4(), uuid4()]

    def interpreter(_events):
        return [InterpretedSignal(
            kind="cohort_weakness",
            summary="Class 10-B weak on Trigonometry prerequisites",
            confidence=0.82,
            evidence_event_ids=ev_ids,
        )]

    def builder(sig: InterpretedSignal):
        signal = CohortWeaknessSignal(
            cohort_label="Class 10-B",
            topic_label="Trigonometry",
            gap_type="prerequisite",
            confidence=sig.confidence,
            evidence=[EvidenceRef(event_id=e, summary="weak attempt") for e in sig.evidence_event_ids],
            owner_role="teacher",
            owner_ref=owner,
        )
        return build_cohort_weakness_recommendation(signal)

    cycle = WorkflowCycle(ledger=ledger, interpreters=[interpreter],
                          builders={"cohort_weakness": builder})

    events = [ObservedEvent(event_id=e, canonical_uuid=uuid4(),
                            type="score.recorded", payload={"score": 0.3}) for e in ev_ids]
    recs = cycle.run(events)
    assert len(recs) == 1
    rec = recs[0]

    # Step 4-5: gate. Non-consequential prepare-style rec; surfaced, not auto-performed.
    state = cycle.approve(rec)
    result = cycle.execute(rec)
    # Step 6-7: outcome + learn close the loop.
    oc = outcome(rec, result, effective=True, summary="support prepared and used")
    note = learn("cohort_weakness", oc)
    assert note.signal_strength_delta > 0
