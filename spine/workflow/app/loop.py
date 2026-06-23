"""The seven-step proactive cycle as composable functions.

    observe(events) -> interpret(signals) -> recommend()
        -> approve() -> execute() -> outcome() -> learn()

Each step is a pure-ish function over plain data so any module (scheduling,
teaching, parent comms, ...) can wire its own observers/interpreters/executors in
while the spine guarantees the ladder and the approval gate.

The keystone, INVARIANT 8: ``execute`` REFUSES to act on a consequential /
execute_with_permission recommendation unless the approval ledger says it is
cleared by a human. And even then, ``execute`` returns an ExecutionResult — a
*clearance*, not a side effect. The actual send/submit/publish/delete/charge/
grade is performed by a governed, credentialled capability behind the gateway;
agents in this package hold no credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol
from uuid import UUID

from .approvals import ApprovalLedger, ApprovalState
from .models import (
    ApprovalDecision,
    LadderStage,
    Recommendation,
    grants_execution,
)
from .permission import ActionDescriptor, LadderPolicy, classify_action


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Step 1 — observe: take raw attributed events into the loop's working set.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ObservedEvent:
    """A behavioural event observed by the loop.

    Carries only the opaque canonical_uuid (INVARIANT 1/2) and the event ref;
    the loop never holds PII. ``payload`` is the already-validated, PII-free
    event body summary the upstream service exposed.
    """

    event_id: UUID
    canonical_uuid: UUID
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime | None = None


def observe(events: list[ObservedEvent]) -> list[ObservedEvent]:
    """Step 1: gather the events to reason over.

    Pure pass-through with a PII guard: refuse anything that smells like raw PII
    leaking into the working set. The loop reasons over opaque refs only.
    """
    _PII_KEYS = {"name", "email", "phone", "address", "dob", "full_name"}
    for ev in events:
        leaked = _PII_KEYS.intersection({k.lower() for k in ev.payload})
        if leaked:
            raise ValueError(
                f"Observed event {ev.event_id} carries forbidden PII keys {sorted(leaked)}; "
                "behavioural data carries only the opaque canonical_uuid (INVARIANT 1/2)."
            )
    return list(events)


# ---------------------------------------------------------------------------
# Step 2 — interpret: turn observed events into interpreted signals.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class InterpretedSignal:
    """A signal an interpreter derived from observed evidence.

    ``kind`` names the signal (e.g. 'cohort_weakness'). ``confidence`` is the
    interpreter's confidence in [0,1]. ``evidence_event_ids`` is the lineage:
    a judgment is NEVER drawn from a single bad score — interpreters that draw a
    learner judgment must corroborate (see ``corroborated``).
    """

    kind: str
    summary: str
    confidence: float
    evidence_event_ids: list[UUID]
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def corroborated(self) -> bool:
        """True when more than one piece of evidence backs the signal."""
        return len(self.evidence_event_ids) > 1


Interpreter = Callable[[list[ObservedEvent]], list[InterpretedSignal]]


def interpret(
    events: list[ObservedEvent],
    interpreters: list[Interpreter],
    *,
    require_corroboration: bool = True,
) -> list[InterpretedSignal]:
    """Step 2: run interpreters over the observed events.

    INVARIANT (CORE correctness): a learner judgment is never confirmed from a
    single bad score. When ``require_corroboration`` is set, single-evidence
    signals are dropped rather than promoted — they may still be observed again
    and corroborated on a later cycle.
    """
    signals: list[InterpretedSignal] = []
    for fn in interpreters:
        for sig in fn(events):
            if not sig.evidence_event_ids:
                raise ValueError(
                    f"Interpreted signal '{sig.kind}' carries no evidence; signals "
                    "must be evidence-backed (no opaque claims)."
                )
            if require_corroboration and not sig.corroborated:
                continue
            signals.append(sig)
    return signals


# ---------------------------------------------------------------------------
# Step 3 — recommend: turn signals into Recommendation objects.
# ---------------------------------------------------------------------------
RecommendationBuilder = Callable[[InterpretedSignal], Recommendation | None]


def recommend(
    signals: list[InterpretedSignal],
    builders: dict[str, RecommendationBuilder],
) -> list[Recommendation]:
    """Step 3: dispatch each signal to its registered builder.

    A builder returns a fully-provenanced Recommendation (or None to skip). The
    Recommendation model and the ladder classification jointly guarantee a
    consequential recommendation is never minted as safe_automatic.
    """
    out: list[Recommendation] = []
    for sig in signals:
        builder = builders.get(sig.kind)
        if builder is None:
            continue
        rec = builder(sig)
        if rec is not None:
            out.append(rec)
    return out


# ---------------------------------------------------------------------------
# Step 4 — approve: the human gate. We open the recommendation as PENDING and
# (when a decision is supplied) record it. This module NEVER self-approves.
# ---------------------------------------------------------------------------
def approve(
    recommendation: Recommendation,
    ledger: ApprovalLedger,
    *,
    decision: ApprovalDecision | None = None,
) -> ApprovalState:
    """Step 4: open the recommendation for human decision and optionally record
    a decision a human has already made.

    Opening is idempotent-safe per ledger: if already open, we keep the existing
    trail. A decision, when supplied, must reference this recommendation and is
    recorded against it. The decision's ``decided_by`` is an opaque HUMAN ref —
    agents hold no credentials and cannot self-approve.
    """
    if ledger.current_state(recommendation.id) is None:
        ledger.open(recommendation.id)

    if decision is not None:
        if decision.recommendation_id != recommendation.id:
            raise ValueError(
                "Approval decision references a different recommendation than the one being approved."
            )
        ledger.record_decision(decision)

    state = ledger.current_state(recommendation.id)
    assert state is not None  # opened above
    return state


# ---------------------------------------------------------------------------
# Step 5 — execute: gated. Returns a CLEARANCE, never a side effect.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ExecutionResult:
    """The result of the execute gate.

    ``cleared`` is True only when the action may proceed. ``performed`` is True
    only for a safe_automatic action the runtime is allowed to fire (and even
    then the actual outward effect is delegated to a governed capability —
    ``capability`` names which). For everything consequential, ``cleared`` means
    'a credentialled, governed capability behind the gateway is now authorised to
    perform it' — this package still performs no side effect.
    """

    recommendation_id: UUID
    cleared: bool
    performed: bool
    stage: LadderStage
    reason: str
    capability: str | None = None
    at: datetime = field(default_factory=_now)


def execute(
    recommendation: Recommendation,
    ledger: ApprovalLedger,
    *,
    action: ActionDescriptor | None = None,
    policy: LadderPolicy | None = None,
    capability: str | None = None,
) -> ExecutionResult:
    """Step 5: the permission gate.

    Rules (INVARIANT 8):
      * A consequential / execute_with_permission recommendation is cleared ONLY
        when the ledger says a human approved (or adjusted) it. Otherwise it is
        refused. It NEVER auto-fires.
      * A safe_automatic, non-consequential recommendation may be cleared and
        marked performed without a human — but only if a re-classification of
        the action still agrees it is safe_automatic (defence in depth).
      * recommend / prepare stages are never executed here; they are surfaced /
        staged for a human.
    """
    stage = LadderStage(recommendation.ladder_stage)

    # Defence in depth: re-classify the action if one is supplied and confirm it
    # agrees with the recommendation's recorded stage. A mismatch fails closed.
    if action is not None:
        reclassified = classify_action(action, policy)
        if recommendation.is_consequential and not reclassified.is_consequential:
            # Trust the stricter view.
            pass
        if reclassified.is_consequential and stage == LadderStage.SAFE_AUTOMATIC:
            return ExecutionResult(
                recommendation_id=recommendation.id,
                cleared=False,
                performed=False,
                stage=stage,
                reason=(
                    "Re-classification found the action consequential while the "
                    "recommendation claims safe_automatic; refusing (fail closed)."
                ),
            )

    if recommendation.is_consequential or stage == LadderStage.EXECUTE_WITH_PERMISSION:
        if ledger.is_cleared(recommendation.id):
            return ExecutionResult(
                recommendation_id=recommendation.id,
                cleared=True,
                performed=False,  # delegated to a governed capability; not done here
                stage=stage,
                reason=(
                    "Human approval recorded; a governed, credentialled capability "
                    "behind the gateway is authorised to perform this action."
                ),
                capability=capability,
            )
        return ExecutionResult(
            recommendation_id=recommendation.id,
            cleared=False,
            performed=False,
            stage=stage,
            reason=(
                "Consequential action without a recorded human approval; refused. "
                "INVARIANT 8: it can never auto-fire."
            ),
        )

    if stage == LadderStage.SAFE_AUTOMATIC:
        return ExecutionResult(
            recommendation_id=recommendation.id,
            cleared=True,
            performed=True,
            stage=stage,
            reason="Low-risk, in-policy, non-consequential; performed unattended with audit.",
            capability=capability,
        )

    # recommend / prepare: surfaced or staged, not executed.
    return ExecutionResult(
        recommendation_id=recommendation.id,
        cleared=False,
        performed=False,
        stage=stage,
        reason=(
            f"Stage '{stage.value}' is not an execution stage; the recommendation "
            "is surfaced/staged for a human, not performed."
        ),
    )


# ---------------------------------------------------------------------------
# Step 6 — outcome: record what actually happened after execution.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Outcome:
    """The observed outcome of an executed recommendation.

    ``effective`` is the human/measured judgment of whether the action helped.
    ``observed_event_ids`` links the follow-on evidence that informs the next
    cycle — closing the loop.
    """

    recommendation_id: UUID
    executed: bool
    effective: bool | None
    summary: str
    observed_event_ids: list[UUID] = field(default_factory=list)
    at: datetime = field(default_factory=_now)


def outcome(
    recommendation: Recommendation,
    execution: ExecutionResult,
    *,
    effective: bool | None = None,
    summary: str = "",
    observed_event_ids: list[UUID] | None = None,
) -> Outcome:
    """Step 6: capture the outcome of an execution for the learn step."""
    return Outcome(
        recommendation_id=recommendation.id,
        executed=execution.cleared,
        effective=effective,
        summary=summary or execution.reason,
        observed_event_ids=observed_event_ids or [],
    )


# ---------------------------------------------------------------------------
# Step 7 — learn: derive an adjustment signal from the outcome.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LearningNote:
    """A note the loop produces to improve future cycles.

    Deliberately conservative: it suggests confidence/policy nudges as data, it
    does NOT silently re-tune the ladder. Any change to what may auto-fire is a
    policy decision a human owns.
    """

    recommendation_kind: str
    signal_strength_delta: float
    rationale: str
    at: datetime = field(default_factory=_now)


def learn(
    signal_kind: str,
    outcome_record: Outcome,
) -> LearningNote:
    """Step 7: turn an outcome into a (human-reviewable) learning note.

    Effective outcomes nudge confidence up; ineffective ones nudge it down;
    unexecuted/declined outcomes are neutral. The magnitude is small and the
    note is advisory — it never re-rungs an action by itself.
    """
    if outcome_record.effective is True:
        delta, why = 0.05, "Outcome was effective; reinforce this signal->recommendation mapping."
    elif outcome_record.effective is False:
        delta, why = -0.05, "Outcome was not effective; weaken this mapping and revisit interpretation."
    else:
        delta, why = 0.0, "No measured outcome (not executed or not yet observed); no adjustment."
    return LearningNote(
        recommendation_kind=signal_kind,
        signal_strength_delta=delta,
        rationale=why,
    )


# ---------------------------------------------------------------------------
# The composed cycle — a thin orchestrator wiring the seven steps together.
# ---------------------------------------------------------------------------
@dataclass
class WorkflowCycle:
    """Composes the seven steps with the pluggable parts a module supplies.

    A module provides its interpreters and builders; the spine supplies the
    ladder, the approval ledger, and the gated execute. ``run`` performs steps
    1-3 (observe -> interpret -> recommend) which are always safe; approval,
    execution, outcome and learning are driven explicitly by the caller so the
    human gate is never bypassed by a single convenience call.
    """

    ledger: ApprovalLedger
    interpreters: list[Interpreter]
    builders: dict[str, RecommendationBuilder]
    policy: LadderPolicy | None = None
    require_corroboration: bool = True

    def run(self, events: list[ObservedEvent]) -> list[Recommendation]:
        observed = observe(events)
        signals = interpret(
            observed, self.interpreters, require_corroboration=self.require_corroboration
        )
        return recommend(signals, self.builders)

    def approve(
        self, recommendation: Recommendation, decision: ApprovalDecision | None = None
    ) -> ApprovalState:
        return approve(recommendation, self.ledger, decision=decision)

    def execute(
        self,
        recommendation: Recommendation,
        *,
        action: ActionDescriptor | None = None,
        capability: str | None = None,
    ) -> ExecutionResult:
        return execute(
            recommendation,
            self.ledger,
            action=action,
            policy=self.policy,
            capability=capability,
        )
