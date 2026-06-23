"""Pydantic mirrors of the recommendation contract (contracts/src/recommendations/*).

A faithful port of the Zod schemas: the four-rung LadderStage, the
Recommendation object with full provenance (evidence, confidence, owner, due
date, consequence, why-am-i-seeing-this), and the ApprovalDecision a human
records against it.

INVARIANT 8 is carried in the shape itself: a consequential recommendation can
never be ``safe_automatic`` (the model rejects it). INVARIANT 1/2: owner.ref and
decided_by are opaque canonical refs only — never PII.

The runtime spelling uses underscores (``execute_with_permission``); the
event-layer ``PermissionRung`` uses hyphens. ``rung_to_event_rung`` /
``event_rung_to_stage`` map the two one-to-one at the boundary.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class LadderStage(str, Enum):
    """The permission-ladder stage of a recommendation (runtime spelling)."""

    RECOMMEND = "recommend"  # surface it; the human decides everything
    PREPARE = "prepare"  # draft/stage the action but do not perform it
    EXECUTE_WITH_PERMISSION = "execute_with_permission"  # ready — only after explicit approval
    SAFE_AUTOMATIC = "safe_automatic"  # low-risk, in-policy; may proceed unattended


#: Documentation per stage (mirrors LADDER_STAGE_DOCS in the contract).
LADDER_STAGE_DOCS: dict[str, str] = {
    LadderStage.RECOMMEND.value: (
        "Surface the finding and the suggested action; the human decides and acts."
    ),
    LadderStage.PREPARE.value: (
        "Draft or stage the action (e.g. compose the message, build the paper) "
        "without performing it."
    ),
    LadderStage.EXECUTE_WITH_PERMISSION.value: (
        "The action is prepared and the agent can perform it, but ONLY once a "
        "human approves. Consequential actions live here and never auto-fire."
    ),
    LadderStage.SAFE_AUTOMATIC.value: (
        "Low-risk, in-policy actions the system may perform unattended, with a "
        "full audit trail."
    ),
}

#: One-to-one map to the event-layer PermissionRung (hyphen-cased).
_STAGE_TO_EVENT_RUNG: dict[str, str] = {
    LadderStage.RECOMMEND.value: "recommend",
    LadderStage.PREPARE.value: "prepare",
    LadderStage.EXECUTE_WITH_PERMISSION.value: "execute-with-permission",
    LadderStage.SAFE_AUTOMATIC.value: "safe-automatic",
}
_EVENT_RUNG_TO_STAGE: dict[str, str] = {v: k for k, v in _STAGE_TO_EVENT_RUNG.items()}


def rung_to_event_rung(stage: "LadderStage | str") -> str:
    """Translate a runtime LadderStage to the hyphen-cased event PermissionRung."""
    value = stage.value if isinstance(stage, LadderStage) else str(stage)
    return _STAGE_TO_EVENT_RUNG[value]


def event_rung_to_stage(rung: str) -> LadderStage:
    """Translate a hyphen-cased event PermissionRung back to a LadderStage."""
    return LadderStage(_EVENT_RUNG_TO_STAGE[rung])


class RecommendationConfidenceBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalDecisionKind(str, Enum):
    APPROVE = "approve"
    ADJUST = "adjust"
    DECLINE = "decline"


class RecommendationOwner(_Model):
    """Who owns / must approve the recommendation — a role plus an opaque ref."""

    role: str = Field(
        description="The role responsible, e.g. 'teacher', 'coordinator'. Never a real person's name."
    )
    ref: UUID = Field(description="Opaque canonical ref to the responsible person. Never PII.")


class EvidenceRef(_Model):
    """A linked piece of evidence supporting the recommendation — full lineage."""

    event_id: UUID = Field(description="The attributed event this evidence comes from.")
    summary: str = Field(description="One-line, plain-language description of what this evidence shows.")


class Recommendation(_Model):
    """The proactive recommendation.

    Never auto-fires for consequential actions: the validator enforces that a
    consequential recommendation can never be ``safe_automatic`` — it must wait
    for a human approval decision (carried by ApprovalDecision, never implied).
    """

    id: UUID
    evidence_summary: str = Field(
        description="Plain-language summary of the evidence behind this recommendation."
    )
    evidence_refs: list[EvidenceRef] = Field(
        min_length=1, description="Linked evidence events — never an opaque claim."
    )
    confidence_band: RecommendationConfidenceBand
    owner: RecommendationOwner
    due_date: datetime | None = Field(
        default=None, description="When the action is needed by, when time-bound."
    )
    consequence_of_ignoring: str = Field(
        description="Plain-language statement of what happens if this is not actioned."
    )
    why_am_i_seeing_this: str = Field(
        description="The explainability line: why this surfaced to this owner now."
    )
    suggested_action: str = Field(description="The concrete next step being recommended.")
    ladder_stage: LadderStage
    is_consequential: bool = Field(
        description=(
            "True when acting sends/submits/publishes/deletes/charges/grades. "
            "Consequential actions never auto-fire."
        )
    )

    @model_validator(mode="after")
    def _consequential_never_automatic(self) -> "Recommendation":
        # Mirrors the Zod superRefine: the keystone INVARIANT 8 guarantee.
        if self.is_consequential and self.ladder_stage == LadderStage.SAFE_AUTOMATIC.value:
            raise ValueError(
                "A consequential recommendation can never be safe_automatic; it "
                "must wait for human approval."
            )
        return self


class ApprovalDecision(_Model):
    """The human's decision on a recommendation.

    An ``execute_with_permission`` action may proceed ONLY when an ``approve``
    (or ``adjust``) decision exists, recorded by a human. Agents hold no
    credentials and cannot self-approve.
    """

    recommendation_id: UUID
    decision: ApprovalDecisionKind
    decided_by: UUID = Field(
        description=(
            "Opaque canonical ref to the human who decided. Agents hold no "
            "credentials and cannot self-approve."
        )
    )
    decided_at: datetime
    adjustment: str | None = Field(
        default=None, description="What the human changed, required when the decision is 'adjust'."
    )
    note: str | None = Field(default=None, description="Optional rationale for the audit trail.")

    @model_validator(mode="after")
    def _adjust_requires_adjustment(self) -> "ApprovalDecision":
        if self.decision == ApprovalDecisionKind.ADJUST.value and not self.adjustment:
            raise ValueError("An 'adjust' decision requires an adjustment description.")
        return self


def grants_execution(decision: ApprovalDecision) -> bool:
    """True when this human decision clears an execute_with_permission action."""
    return decision.decision in (
        ApprovalDecisionKind.APPROVE.value,
        ApprovalDecisionKind.ADJUST.value,
    )
