"""Classess Workflow Engine — the proactive loop + permission-ladder runtime (spine A5).

Every module's proactive behaviour runs on this seven-step cycle:

    observe(events) -> interpret(signals) -> recommend() -> approve()
        -> execute() -> outcome() -> learn()

INVARIANT 8 (the permission ladder) is enforced here as runtime, not merely as a
data shape. An action is classified onto a rung
(recommend | prepare | execute_with_permission | safe_automatic). Anything that
sends, submits, publishes, deletes, charges, or grades is CONSEQUENTIAL: it can
never be safe_automatic and CANNOT auto-fire. It sits at execute_with_permission
and waits for an explicit human approval decision before ``execute`` will act.

INVARIANT 1/2: recommendations carry only opaque canonical refs (owner.ref,
decided_by) — never PII. The plain-language fields are about the cohort/finding,
not the person.

This package WRITES no side effects of its own. ``execute`` returns an
ExecutionResult describing what a credentialled, governed capability (behind the
gateway) is cleared to do; agents hold no credentials and never perform the
send/submit/publish/delete/charge/grade themselves.
"""

from __future__ import annotations

from .approvals import (
    ApprovalLedger,
    ApprovalRecord,
    ApprovalState,
    InMemoryApprovalLedger,
)
from .events import (
    WORKFLOW_APP,
    CollectingSink,
    EventRefused,
    WorkflowEvent,
    WorkflowEventSink,
    WorkflowEventType,
    action_executed,
    approval_events_from_trail,
    approval_given,
    emit,
    recommendation_actioned,
    recommendation_created,
)
from .loop import (
    ExecutionResult,
    InterpretedSignal,
    LearningNote,
    ObservedEvent,
    Outcome,
    WorkflowCycle,
    execute,
    interpret,
    learn,
    observe,
    outcome,
    recommend,
)
from .models import (
    ApprovalDecision,
    ApprovalDecisionKind,
    EvidenceRef,
    LadderStage,
    Recommendation,
    RecommendationConfidenceBand,
    RecommendationOwner,
)
from .permission import (
    CONSEQUENTIAL_VERBS,
    ActionDescriptor,
    LadderDecision,
    classify_action,
    may_autofire,
)
from .recommendations import (
    CohortWeaknessSignal,
    build_cohort_weakness_recommendation,
    build_recommendation,
)

__all__ = [
    # models
    "LadderStage",
    "RecommendationConfidenceBand",
    "RecommendationOwner",
    "EvidenceRef",
    "Recommendation",
    "ApprovalDecisionKind",
    "ApprovalDecision",
    # permission
    "ActionDescriptor",
    "LadderDecision",
    "CONSEQUENTIAL_VERBS",
    "classify_action",
    "may_autofire",
    # recommendations
    "CohortWeaknessSignal",
    "build_recommendation",
    "build_cohort_weakness_recommendation",
    # approvals
    "ApprovalState",
    "ApprovalRecord",
    "ApprovalLedger",
    "InMemoryApprovalLedger",
    # events (the workflow/proactive boundary — builders the Integration agent wires)
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
    # loop
    "ObservedEvent",
    "InterpretedSignal",
    "ExecutionResult",
    "Outcome",
    "LearningNote",
    "WorkflowCycle",
    "observe",
    "interpret",
    "recommend",
    "execute",
    "outcome",
    "learn",
]
