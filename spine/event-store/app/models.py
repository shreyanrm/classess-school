"""Pydantic mirrors of the event contract (contracts/src/events/*).

This is a faithful port of the Zod schemas: primitives, the six-dimension
mastery model, the ten gap types, the attempt evidence shape, every event
payload, the attribution, and the discriminated-union envelope. EmitEventInput
on the way in, EventEnvelope on the way out — matching
contracts/src/openapi/event-store.ts.

No model here carries PII; canonical_uuid fields are opaque refs only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Primitives (contracts/src/events/primitives.ts)
# ---------------------------------------------------------------------------
EVENT_SCHEMA_VERSION = "v1"

AppId = Literal["school", "learner", "platform"]
Purpose = Literal[
    "instruction",
    "assessment",
    "mastery",
    "intervention",
    "operations",
    "communication",
    "account",
]
EventTypeName = Literal[
    "attempt.recorded",
    "assignment.created",
    "submission.created",
    "score.recorded",
    "mastery.updated",
    "intervention.fired",
    "consent.granted",
    "consent.revoked",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OntologyRef(_Model):
    topic_id: UUID = Field(description="Ontology topic node.")
    outcome_id: UUID | None = Field(default=None, description="Learning outcome node.")
    competency_id: UUID | None = Field(default=None, description="Competency node.")
    skill_id: UUID | None = Field(default=None, description="Skill node, finest grain.")


# ---------------------------------------------------------------------------
# Cross-cutting: verification (INVARIANT 7) + permission ladder (INVARIANT 8)
# ---------------------------------------------------------------------------
VerificationStatus = Literal["pending", "passed", "failed", "human-override"]
PermissionRung = Literal["recommend", "prepare", "execute-with-permission", "safe-automatic"]


class VerificationCheck(_Model):
    name: str
    passed: bool
    detail: str | None = None


class Verification(_Model):
    status: VerificationStatus
    confidence: float = Field(ge=0, le=1, description="Verifier confidence in [0,1].")
    gate_threshold: float = Field(ge=0, le=1, description="Confidence gate; below this is refused.")
    checks: list[VerificationCheck] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Mastery model (contracts/src/events/mastery.ts)
# ---------------------------------------------------------------------------
MasteryBand = Literal["not-started", "emerging", "developing", "secure", "independent"]


class MasteryDimensions(_Model):
    performance: float = Field(ge=0, le=1)
    reliability: float = Field(ge=0, le=1)
    independence: float = Field(ge=0, le=1)
    difficulty: float = Field(ge=0, le=1)
    recency: float = Field(ge=0, le=1)
    consistency: float = Field(ge=0, le=1)


class MasteryReading(_Model):
    dimensions: MasteryDimensions
    composite: float = Field(ge=0, le=1, description="Collapsed product for ranking only; never shown raw.")
    band: MasteryBand
    independent: bool


# ---------------------------------------------------------------------------
# Gaps (contracts/src/events/gaps.ts)
# ---------------------------------------------------------------------------
GapType = Literal[
    "prerequisite",
    "conceptual",
    "procedural",
    "application",
    "retention",
    "language",
    "accuracy",
    "speed",
    "confidence",
    "support-dependency",
]


class GapEvidence(_Model):
    gap_type: GapType
    confidence: float = Field(ge=0, le=1)
    confirmed: bool = Field(description="True only once corroborated by sufficient fresh evidence.")
    evidence_event_ids: list[UUID] = Field(min_length=1)
    rationale: str


# ---------------------------------------------------------------------------
# Attempt (contracts/src/events/attempt.ts)
# ---------------------------------------------------------------------------
AttemptMode = Literal["independent", "supported"]
AssistanceLevel = Literal[
    "Learn", "Coach", "Hint", "Work-with-me", "Check-my-work", "Independent"
]


class AttemptPayload(_Model):
    attempt_id: UUID
    question_id: UUID | None = None
    ontology: OntologyRef
    mode: AttemptMode
    assistance_level: AssistanceLevel
    correct: bool
    score: float | None = Field(default=None, ge=0, le=1)
    time_taken_ms: int = Field(ge=0)
    difficulty: float = Field(ge=0, le=1)
    attempt_number: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _mode_assistance_coherence(self) -> "AttemptPayload":
        # Mirrors the Zod superRefine: keystone independence flag must be coherent.
        is_independent_level = self.assistance_level == "Independent"
        if self.mode == "independent" and not is_independent_level:
            raise ValueError("mode 'independent' requires assistance_level 'Independent'.")
        if self.mode == "supported" and is_independent_level:
            raise ValueError("mode 'supported' cannot use assistance_level 'Independent'.")
        return self


# ---------------------------------------------------------------------------
# Remaining payloads (contracts/src/events/payloads.ts)
# ---------------------------------------------------------------------------
class AssignmentCreatedPayload(_Model):
    assignment_id: UUID
    institution_id: UUID
    created_by: UUID = Field(description="Opaque ref to the authoring teacher.")
    ontology: OntologyRef
    title: str
    due_at: datetime | None = None
    verification: Verification | None = None


class SubmissionCreatedPayload(_Model):
    submission_id: UUID
    assignment_id: UUID
    submitted_by: UUID
    attempt_ids: list[UUID]
    submitted_at: datetime


ScoreMode = Literal["post-submission", "scanned-handwriting", "preventive-before-submission"]
ConfidenceBand = Literal["low", "medium", "high"]


class ScoreRecordedPayload(_Model):
    score_id: UUID
    submission_id: UUID
    scored_subject: UUID
    ontology: OntologyRef
    mode: ScoreMode
    raw_score: float = Field(ge=0, le=1)
    confidence_band: ConfidenceBand
    human_final: bool
    verification: Verification | None = None


class MasteryUpdatedPayload(_Model):
    subject: UUID
    ontology: OntologyRef
    reading: MasteryReading
    gaps: list[GapEvidence] = Field(default_factory=list)
    source_event_ids: list[UUID] = Field(default_factory=list)


class InterventionFiredPayload(_Model):
    intervention_id: UUID
    subject: UUID
    owner: UUID
    gap: GapEvidence
    rung: PermissionRung
    approved_by: UUID | None = None
    due_at: datetime | None = None
    consequence: str


AgeTier = Literal["child", "teen", "adult"]


class ConsentGrantedPayload(_Model):
    consent_id: UUID
    scope: str
    purpose: Purpose
    age_tier: AgeTier
    granted_by: UUID


class ConsentRevokedPayload(_Model):
    consent_id: UUID
    revoked_by: UUID
    reason: str | None = None


# ---------------------------------------------------------------------------
# The discriminated union of typed bodies (contracts/src/events/envelope.ts)
# Each member pairs the literal `type` discriminator with its typed payload.
# ---------------------------------------------------------------------------
class _AttemptBody(_Model):
    type: Literal["attempt.recorded"]
    payload: AttemptPayload


class _AssignmentBody(_Model):
    type: Literal["assignment.created"]
    payload: AssignmentCreatedPayload


class _SubmissionBody(_Model):
    type: Literal["submission.created"]
    payload: SubmissionCreatedPayload


class _ScoreBody(_Model):
    type: Literal["score.recorded"]
    payload: ScoreRecordedPayload


class _MasteryBody(_Model):
    type: Literal["mastery.updated"]
    payload: MasteryUpdatedPayload


class _InterventionBody(_Model):
    type: Literal["intervention.fired"]
    payload: InterventionFiredPayload


class _ConsentGrantedBody(_Model):
    type: Literal["consent.granted"]
    payload: ConsentGrantedPayload


class _ConsentRevokedBody(_Model):
    type: Literal["consent.revoked"]
    payload: ConsentRevokedPayload


EventBody = Annotated[
    Union[
        _AttemptBody,
        _AssignmentBody,
        _SubmissionBody,
        _ScoreBody,
        _MasteryBody,
        _InterventionBody,
        _ConsentGrantedBody,
        _ConsentRevokedBody,
    ],
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Attribution + Emit/Envelope (contracts/src/openapi/event-store.ts)
# ---------------------------------------------------------------------------
class EventAttribution(_Model):
    app: AppId
    canonical_uuid: UUID = Field(description="Opaque identity ref (INVARIANT 1, 2).")
    purpose: Purpose
    consent_ref: UUID = Field(description="Consent record this event was captured under (INVARIANT 6).")


class EmitEventInput(EventAttribution):
    """Producer input. The store assigns event_id/recorded_at/schema_version.

    `type` + `payload` are validated as a discriminated union against the
    event contract so no malformed evidence ever enters the immutable store.
    """

    occurred_at: datetime | None = Field(default=None, description="Defaults to now at the store if omitted.")
    type: EventTypeName
    payload: dict = Field(description="Validated against the typed body for `type`.")

    @model_validator(mode="after")
    def _validate_typed_payload(self) -> "EmitEventInput":
        # Re-validate (type, payload) through the discriminated union so the
        # contract is enforced exactly, including the attempt coherence rule.
        from pydantic import TypeAdapter

        adapter: TypeAdapter = TypeAdapter(EventBody)
        adapter.validate_python({"type": self.type, "payload": self.payload})
        return self


class EventEnvelope(EventAttribution):
    """Stored, immutable event."""

    event_id: UUID
    schema_version: Literal["v1"] = "v1"
    occurred_at: datetime
    recorded_at: datetime
    type: EventTypeName
    payload: dict


class ErrorResponse(_Model):
    error: str
    detail: str | None = None
