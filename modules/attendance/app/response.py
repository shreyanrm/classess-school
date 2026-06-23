"""Attendance RESPONSE workflow (d8 "Risk, reconciliation & response").

Detection (``risk.py``) produces SIGNALS. This module turns a confirmed signal
into the human-owned RESPONSE the document names:

  - "repeated student absence triggers parent communication" — emit a
    :class:`ParentCommunicationRequestedEvent` that ASKS the communication
    module to reach a guardian. It is a REQUEST that ``requires_approval``;
    nothing is sent here.
  - "...and a catch-up plan" — build a proposed catch-up plan over the missed
    sessions/subjects for a human to review and own.

PERMISSION LADDER (INVARIANT 8): this module recommends and prepares; it NEVER
auto-fires a consequential action. Parent communication and catch-up
assignment are consequential, so every output carries ``requires_approval`` /
``needs_human_review`` and crosses the boundary only as an event the owning
module gates.

Which risks warrant a response is policy (configurable), not hard-coded: by
default consecutive/chronic absence at CONCERN or worse triggers parent
contact; the exam-shortage signal does too, because it is time-sensitive.

PII-free: opaque ``canonical_uuid`` only. Pure, offline, no provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Sequence

from .events import (
    CatchupPlanProposedEvent,
    ParentCommunicationRequestedEvent,
    catchup_plan_proposed_event,
    parent_communication_requested_event,
)
from .risk import RiskFinding, RiskKind, RiskSeverity

# Severities that, by default, warrant a response. WATCH is too early to
# contact a guardian; CONCERN/URGENT cross the line. Configurable per call.
_DEFAULT_TRIGGER_SEVERITIES = frozenset(
    {RiskSeverity.CONCERN.value, RiskSeverity.URGENT.value}
)
# Risk kinds that justify reaching a guardian about ABSENCE.
_DEFAULT_TRIGGER_KINDS = frozenset(
    {
        RiskKind.CONSECUTIVE.value,
        RiskKind.CHRONIC.value,
        RiskKind.EXAM_SHORTAGE.value,
    }
)


@dataclass(frozen=True)
class ResponseConfig:
    trigger_severities: frozenset = _DEFAULT_TRIGGER_SEVERITIES
    trigger_kinds: frozenset = _DEFAULT_TRIGGER_KINDS


@dataclass(frozen=True)
class CatchupPlan:
    """A PROPOSED recovery plan after repeated absence. Human-owned.

    Lists the missed days/subjects and a plain-language step per subject. It is
    a proposal: ``requires_approval`` stays True until a teacher confirms it.
    """

    canonical_uuid: str
    missed_sessions: int
    subjects: Sequence[str]
    steps: Sequence[str]
    rationale: str
    requires_approval: bool = True


def should_respond(
    finding: RiskFinding, config: Optional[ResponseConfig] = None
) -> bool:
    """True when a finding warrants a (human-gated) response."""

    cfg = config or ResponseConfig()
    return (
        finding.risk_kind in cfg.trigger_kinds
        and finding.severity in cfg.trigger_severities
    )


def parent_communication_for(
    finding: RiskFinding, config: Optional[ResponseConfig] = None
) -> Optional[ParentCommunicationRequestedEvent]:
    """Emit the parent-communication TRIGGER for a qualifying finding.

    Returns ``None`` when the finding does not warrant contact. The event
    ``requires_approval``; the communication module owns consent, language and
    the send gate. Nothing is sent here.
    """

    if not should_respond(finding, config):
        return None
    return parent_communication_requested_event(
        canonical_uuid=finding.canonical_uuid,
        risk_kind=finding.risk_kind,
        severity=finding.severity,
        reason=finding.rationale,
    )


def build_catchup_plan(
    canonical_uuid: str,
    history: Mapping[str, Any],
) -> CatchupPlan:
    """Build a PROPOSED catch-up plan from a learner's attendance history.

    ``history`` is the same shape ``risk.detect_risks`` consumes
    (``{"canonical_uuid", "days": [{"date", "status", "subject"?}, ...]}``).
    Missed days are grouped by subject so a teacher sees what to recover. This
    proposes; it never auto-assigns work (``requires_approval`` stays True).
    """

    days = history.get("days", []) or []
    missed = [d for d in days if str(d.get("status", "")).lower() == "absent"]
    subjects: List[str] = []
    for d in missed:
        subj = d.get("subject")
        if subj and subj not in subjects:
            subjects.append(subj)

    if subjects:
        steps = [
            f"Recover the missed {s} sessions: share notes and a short "
            "catch-up task, then check understanding."
            for s in subjects
        ]
    elif missed:
        steps = [
            "Recover the missed sessions: share notes and a short catch-up "
            "task, then check understanding."
        ]
    else:
        steps = []

    rationale = (
        f"{len(missed)} missed session(s) across "
        f"{len(subjects) if subjects else 'one or more'} subject(s). A teacher "
        "reviews and owns this plan before any work is assigned."
    )
    return CatchupPlan(
        canonical_uuid=canonical_uuid,
        missed_sessions=len(missed),
        subjects=tuple(subjects),
        steps=tuple(steps),
        rationale=rationale,
    )


def catchup_plan_event(plan: CatchupPlan) -> CatchupPlanProposedEvent:
    """Wrap a proposed plan as the boundary-crossing event."""

    return catchup_plan_proposed_event(
        canonical_uuid=plan.canonical_uuid,
        missed_sessions=plan.missed_sessions,
        subjects=plan.subjects,
    )
