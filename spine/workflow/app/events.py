"""Proactive-loop lifecycle events (spine A5 — the workflow boundary).

The workflow engine emits a clean, attributed, consent-stamped event for every
consequential turn of the proactive loop (INVARIANT 5). Four event types live at
the workflow/proactive boundary and mirror the catalog's *workflow/agent* family
in ``contracts/src/events/envelope.ts``:

    recommendation.created   a recommendation was minted from interpreted signals
    recommendation.actioned  a human actioned (approved / adjusted / declined) it
    approval.given           the ApprovalLedger recorded a clearing human decision
    action.executed          the execute gate cleared (and, for safe_automatic,
                             performed) an action

These are OPERATIONAL governance events about the LOOP. They carry only the
opaque ``canonical_uuid`` (the owner / the deciding human) and opaque refs — NO
PII (INVARIANT 1/2). The plain-language strings already on a ``Recommendation``
are about the cohort/finding, never a person.

This module BUILDS events and hands them to an injected sink; it performs NO
direct event-store write and holds NO credentials. The Integration agent wires
the real sink — an authenticated append THROUGH THE GATEWAY (INVARIANT 3) — and
persists. Builders here are pure: same input, same event, no side effect.

The ``ApprovalLedger`` state transitions are exposed as events too:
``approval_events_from_trail`` turns a ledger trail into the ``approval.given``
events for its clearing decisions, so the ledger's state machine is auditable
without this module reaching into the durable store itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal
from uuid import UUID

from .approvals import ApprovalRecord, ApprovalState
from .loop import ExecutionResult
from .models import (
    ApprovalDecision,
    ApprovalDecisionKind,
    LadderStage,
    Recommendation,
    rung_to_event_rung,
)

#: The four workflow/proactive-boundary event types (canonical contract names).
WorkflowEventType = Literal[
    "recommendation.created",
    "recommendation.actioned",
    "approval.given",
    "action.executed",
]

#: The app context these events are emitted under (the proactive loop runtime).
WORKFLOW_APP = "workflow"

#: Keys we refuse to let ride along on a workflow event payload — defence in
#: depth on top of the loop's observe-time PII guard. Opaque refs only.
_PII_KEYS: frozenset[str] = frozenset(
    {"name", "email", "phone", "address", "dob", "full_name", "first_name", "last_name"}
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class EventRefused(ValueError):
    """Raised when a workflow event cannot be built under the invariants."""


def _assert_no_pii(payload: dict[str, Any]) -> None:
    """Backstop: a workflow event carries opaque refs only (INVARIANT 1/2)."""
    leaked = _PII_KEYS.intersection({str(k).lower() for k in payload})
    if leaked:
        raise EventRefused(
            f"Workflow event payload carries forbidden PII keys {sorted(leaked)}; "
            "the loop emits only opaque canonical refs (INVARIANT 1/2)."
        )


@dataclass(frozen=True)
class WorkflowEvent:
    """An immutable workflow-loop event.

    ``canonical_uuid`` is the opaque ref the event is attributed to (the owner of
    the recommendation, or the human who decided). ``payload`` is PII-free.
    Produced, never mutated — there is no setter and the dataclass is frozen.
    """

    type: WorkflowEventType
    canonical_uuid: UUID
    occurred_at: datetime
    payload: dict[str, Any]

    def as_emit_input(self, *, purpose: str, consent_ref: str, app: str = WORKFLOW_APP) -> dict[str, Any]:
        """Shape this event as the event-store ``EmitEventInput`` the gateway
        accepts: ``{app, canonical_uuid, purpose, consent_ref, occurred_at,
        type, payload}``. CONSENT stamps the write (INVARIANT 6) — the Integration
        agent supplies the purpose + consent_ref it captured the action under.
        """
        if not consent_ref:
            raise EventRefused("consent_ref is required — consent stamps every write (INVARIANT 6).")
        return {
            "app": app,
            "canonical_uuid": str(self.canonical_uuid),
            "purpose": purpose,
            "consent_ref": consent_ref,
            "occurred_at": self.occurred_at.isoformat(),
            "type": self.type,
            "payload": dict(self.payload),
        }


# ---------------------------------------------------------------------------
# recommendation.created — a recommendation was minted (step 3 boundary).
# ---------------------------------------------------------------------------
def recommendation_created(
    recommendation: Recommendation,
    *,
    occurred_at: datetime | None = None,
) -> WorkflowEvent:
    """Build the event for a freshly minted recommendation.

    Attributed to the recommendation owner's opaque ref. The payload mirrors the
    recommendation's provenance summary — confidence band, ladder rung (in the
    hyphen-cased event spelling), consequence flag, evidence event ids — never
    the owner's identity beyond the opaque ref.
    """
    payload: dict[str, Any] = {
        "recommendation_id": str(recommendation.id),
        "owner_role": recommendation.owner.role,
        "confidence_band": recommendation.confidence_band,
        "rung": rung_to_event_rung(recommendation.ladder_stage),
        "is_consequential": recommendation.is_consequential,
        "evidence_event_ids": [str(ref.event_id) for ref in recommendation.evidence_refs],
        "evidence_count": len(recommendation.evidence_refs),
        "requires_human_approval": (
            recommendation.is_consequential
            or recommendation.ladder_stage == LadderStage.EXECUTE_WITH_PERMISSION.value
        ),
    }
    if recommendation.due_date is not None:
        payload["due_date"] = recommendation.due_date.isoformat()
    _assert_no_pii(payload)
    return WorkflowEvent(
        type="recommendation.created",
        canonical_uuid=recommendation.owner.ref,
        occurred_at=occurred_at or _now(),
        payload=payload,
    )


# ---------------------------------------------------------------------------
# recommendation.actioned — a human actioned the recommendation (step 4).
# ---------------------------------------------------------------------------
def recommendation_actioned(
    decision: ApprovalDecision,
    *,
    occurred_at: datetime | None = None,
) -> WorkflowEvent:
    """Build the event for a human actioning a recommendation.

    Records WHO (opaque ref) decided and HOW (approve / adjust / decline) and
    WHEN. Attributed to the deciding human's opaque ref. Agents hold no
    credentials and never self-approve — ``decided_by`` is always a human ref.
    """
    payload: dict[str, Any] = {
        "recommendation_id": str(decision.recommendation_id),
        "decision": decision.decision,
        "decided_by": str(decision.decided_by),
        "clears_execution": _decision_clears(decision),
    }
    if decision.adjustment:
        payload["adjustment"] = decision.adjustment
    if decision.note:
        payload["note"] = decision.note
    _assert_no_pii(payload)
    return WorkflowEvent(
        type="recommendation.actioned",
        canonical_uuid=decision.decided_by,
        occurred_at=occurred_at or decision.decided_at,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# approval.given — the ApprovalLedger recorded a clearing human decision.
# ---------------------------------------------------------------------------
def _decision_clears(decision: ApprovalDecision) -> bool:
    return decision.decision in (
        ApprovalDecisionKind.APPROVE.value,
        ApprovalDecisionKind.ADJUST.value,
    )


def approval_given(
    decision: ApprovalDecision,
    *,
    resulting_state: ApprovalState | str | None = None,
    occurred_at: datetime | None = None,
) -> WorkflowEvent:
    """Build the ``approval.given`` event for a clearing human decision.

    Only an ``approve`` or ``adjust`` grants execution — those are the decisions
    that clear an ``execute_with_permission`` action. A ``decline`` does not
    grant approval, so building an ``approval.given`` for it is refused; surface
    that as ``recommendation.actioned`` (declined) instead.
    """
    if not _decision_clears(decision):
        raise EventRefused(
            f"Decision '{decision.decision}' does not grant approval; only "
            "'approve'/'adjust' clear an action. Use recommendation.actioned "
            "for a decline."
        )
    state = (
        resulting_state.value
        if isinstance(resulting_state, ApprovalState)
        else (resulting_state or _state_for_decision(decision))
    )
    payload: dict[str, Any] = {
        "recommendation_id": str(decision.recommendation_id),
        "decision": decision.decision,
        "approved_by": str(decision.decided_by),
        "resulting_state": state,
        "grants_execution": True,
    }
    if decision.adjustment:
        payload["adjustment"] = decision.adjustment
    _assert_no_pii(payload)
    return WorkflowEvent(
        type="approval.given",
        canonical_uuid=decision.decided_by,
        occurred_at=occurred_at or decision.decided_at,
        payload=payload,
    )


def _state_for_decision(decision: ApprovalDecision) -> str:
    return (
        ApprovalState.APPROVED.value
        if decision.decision == ApprovalDecisionKind.APPROVE.value
        else ApprovalState.ADJUSTED.value
    )


def approval_events_from_trail(records: list[ApprovalRecord]) -> list[WorkflowEvent]:
    """Expose the ApprovalLedger's state transitions as ``approval.given`` events.

    Walks a recorded trail (``ledger.trail(rec_id)``) and emits one
    ``approval.given`` for each transition into a CLEARING state (approved /
    adjusted). The opening PENDING entry and a terminal DECLINED carry no
    decision that grants execution, so they produce no approval.given — the
    ledger's clearing transitions are made auditable without this module touching
    the durable store.
    """
    out: list[WorkflowEvent] = []
    for record in records:
        if record.decision is None:
            continue  # the initial PENDING entry — no human decision yet
        if record.clears_execution and _decision_clears(record.decision):
            out.append(
                approval_given(
                    record.decision,
                    resulting_state=record.state,
                    occurred_at=record.recorded_at,
                )
            )
    return out


# ---------------------------------------------------------------------------
# action.executed — the execute gate cleared / performed an action (step 5).
# ---------------------------------------------------------------------------
def action_executed(
    result: ExecutionResult,
    *,
    owner_ref: UUID,
    occurred_at: datetime | None = None,
) -> WorkflowEvent:
    """Build the ``action.executed`` event for a cleared execution.

    Only a CLEARED ExecutionResult yields an event — a refused gate (no human
    approval, fail-closed reclassification) executed nothing and so emits no
    action.executed. ``performed`` distinguishes a safe_automatic action the
    runtime fired unattended from a consequential clearance delegated to a
    governed, credentialled capability behind the gateway (this package performs
    no outward side effect itself). Attributed to the recommendation owner ref.
    """
    if not result.cleared:
        raise EventRefused(
            "Execution was not cleared; nothing executed, so no action.executed "
            f"event. Gate reason: {result.reason}"
        )
    stage = result.stage.value if isinstance(result.stage, LadderStage) else str(result.stage)
    payload: dict[str, Any] = {
        "recommendation_id": str(result.recommendation_id),
        "rung": rung_to_event_rung(stage),
        "performed": result.performed,
        "delegated": not result.performed,
        "reason": result.reason,
    }
    if result.capability:
        payload["capability"] = result.capability
    _assert_no_pii(payload)
    return WorkflowEvent(
        type="action.executed",
        canonical_uuid=owner_ref,
        occurred_at=occurred_at or result.at,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Sink — anything that consumes a WorkflowEvent (the gateway append, audit).
# ---------------------------------------------------------------------------
WorkflowEventSink = Callable[[WorkflowEvent], None]


@dataclass
class CollectingSink:
    """A simple in-memory sink for tests / dev. Append-only."""

    events: list[WorkflowEvent] = field(default_factory=list)

    def __call__(self, event: WorkflowEvent) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [e.type for e in self.events]


def emit(event: WorkflowEvent, sink: WorkflowEventSink | None = None) -> dict[str, Any]:
    """Hand a built event to an injected sink (if wired).

    Mirrors ``integration.emit_activity``'s degrade contract: with no sink the
    event is returned with ``degraded: True`` (offline / deterministic path); the
    Integration agent wires the real sink that appends through the gateway. This
    module never writes the store directly.
    """
    if sink is None:
        return {"event": event, "emitted": False, "degraded": True}
    sink(event)
    return {"event": event, "emitted": True, "degraded": False}


__all__ = [
    "WorkflowEventType",
    "WORKFLOW_APP",
    "EventRefused",
    "WorkflowEvent",
    "recommendation_created",
    "recommendation_actioned",
    "approval_given",
    "approval_events_from_trail",
    "action_executed",
    "WorkflowEventSink",
    "CollectingSink",
    "emit",
]
