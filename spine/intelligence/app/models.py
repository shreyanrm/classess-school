"""Pydantic mirrors of the event/evidence + ontology contracts.

A faithful, board-agnostic port of the parts of ``contracts/src/events/*`` and
``contracts/src/ontology/*`` that the intelligence engine consumes and produces:

  - the attempt evidence shape (the keystone independent-vs-supported flag),
  - the score-recorded shape (corroborating evidence for gaps),
  - the six explicit mastery dimensions and the plain-language bands,
  - the ten gap types and the GapEvidence lineage envelope,
  - the prerequisite ontology graph used for prerequisite-gap detection.

INVARIANT 1 + 2: nothing here carries PII. ``canonical_uuid`` and ``subject``
fields are opaque random refs; the topic ids are opaque ontology tokens. The
engine never authors mastery directly — it REPLAYS these events to derive state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


# ---------------------------------------------------------------------------
# Ontology reference (contracts/src/events/primitives.ts OntologyRef)
# ---------------------------------------------------------------------------
class OntologyRef(_Model):
    topic_id: UUID = Field(description="Ontology topic node.")
    outcome_id: UUID | None = Field(default=None, description="Learning outcome node.")
    competency_id: UUID | None = Field(default=None, description="Competency node.")
    skill_id: UUID | None = Field(default=None, description="Skill node, finest grain.")


# ---------------------------------------------------------------------------
# Mastery model (contracts/src/events/mastery.ts)
# ---------------------------------------------------------------------------
MASTERY_DIMENSION_KEYS = (
    "performance",
    "reliability",
    "independence",
    "difficulty",
    "recency",
    "consistency",
)

# Plain-language bands shown to humans — the raw formula is NEVER shown.
MasteryBand = Literal["not-started", "emerging", "developing", "secure", "independent"]


class MasteryDimensions(_Model):
    """The six explicit dimensions, each in [0,1]. Never collapsed for learners."""

    performance: float = Field(ge=0, le=1)
    reliability: float = Field(ge=0, le=1)
    independence: float = Field(ge=0, le=1)
    difficulty: float = Field(ge=0, le=1)
    recency: float = Field(ge=0, le=1)
    consistency: float = Field(ge=0, le=1)


class MasteryReading(_Model):
    dimensions: MasteryDimensions
    composite: float = Field(
        ge=0,
        le=1,
        description="Collapsed product for ranking only; never shown raw to a learner.",
    )
    band: MasteryBand
    independent: bool = Field(
        description="True when the learner has crossed into independent demonstration."
    )


class MasteryWeights(_Model):
    """Multiplicative exponents per dimension. Defaults uniform (a plain product)."""

    performance: float = Field(default=1.0, gt=0)
    reliability: float = Field(default=1.0, gt=0)
    independence: float = Field(default=1.0, gt=0)
    difficulty: float = Field(default=1.0, gt=0)
    recency: float = Field(default=1.0, gt=0)
    consistency: float = Field(default=1.0, gt=0)


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

GAP_TYPES: tuple[GapType, ...] = (
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
)


class GapEvidence(_Model):
    gap_type: GapType
    confidence: float = Field(ge=0, le=1)
    confirmed: bool = Field(
        description="True only once corroborated by sufficient fresh evidence; never from a single attempt."
    )
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
    mode: AttemptMode = Field(description="The keystone independent-vs-supported flag.")
    assistance_level: AssistanceLevel
    correct: bool
    score: float | None = Field(default=None, ge=0, le=1)
    time_taken_ms: int = Field(ge=0)
    difficulty: float = Field(ge=0, le=1)
    attempt_number: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _mode_assistance_coherence(self) -> "AttemptPayload":
        is_independent_level = self.assistance_level == "Independent"
        if self.mode == "independent" and not is_independent_level:
            raise ValueError("mode 'independent' requires assistance_level 'Independent'.")
        if self.mode == "supported" and is_independent_level:
            raise ValueError("mode 'supported' cannot use assistance_level 'Independent'.")
        return self

    @property
    def effective_score(self) -> float:
        """Partial-credit score when present, else 1.0/0.0 from correctness."""
        if self.score is not None:
            return self.score
        return 1.0 if self.correct else 0.0


# ---------------------------------------------------------------------------
# Score (contracts/src/events/payloads.ts ScoreRecordedPayload) — corroboration
# ---------------------------------------------------------------------------
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
    # verification omitted from the projection input — the store validated it.


# ---------------------------------------------------------------------------
# The event envelope the engine REPLAYS. A trimmed-but-faithful mirror of
# EventEnvelope (contracts/src/events/envelope.ts). The engine only needs to
# read attempt.recorded and score.recorded; other types pass through untouched.
# ---------------------------------------------------------------------------
class EventEnvelope(_Model):
    """An immutable stored event the engine replays. Append-only at the source."""

    event_id: UUID
    schema_version: Literal["v1"] = "v1"
    occurred_at: datetime
    recorded_at: datetime
    app: AppId
    canonical_uuid: UUID = Field(description="Opaque identity ref (INVARIANT 1, 2).")
    purpose: Purpose
    consent_ref: UUID
    type: EventTypeName
    payload: dict

    def attempt(self) -> AttemptPayload | None:
        if self.type == "attempt.recorded":
            return AttemptPayload.model_validate(self.payload)
        return None

    def score(self) -> ScoreRecordedPayload | None:
        if self.type == "score.recorded":
            return ScoreRecordedPayload.model_validate(self.payload)
        return None


# ---------------------------------------------------------------------------
# Ontology prerequisite graph (contracts/src/ontology/types.ts) — only the
# pieces the prerequisite-gap rule needs: topic ids and confirmed edges.
# ---------------------------------------------------------------------------
PrerequisiteKind = Literal["hard", "soft"]


class PrerequisiteEdge(_Model):
    from_topic_id: UUID = Field(description="The prerequisite topic — must be secure first.")
    to_topic_id: UUID = Field(description="The dependent topic — rests on the prerequisite.")
    kind: PrerequisiteKind
    confirmed: bool = Field(
        description="Only confirmed edges are trusted for routing (A2 steward-validated)."
    )
    rationale: str = ""


class PrerequisiteGraph(_Model):
    """The confirmed prerequisite edges. Proposed (unconfirmed) edges are kept
    but never used for gap routing — mirrors the A2 ownership rule."""

    edges: list[PrerequisiteEdge] = Field(default_factory=list)

    def prerequisites_of(self, topic_id: UUID, *, trusted_only: bool = True) -> list[PrerequisiteEdge]:
        """Edges pointing INTO ``topic_id`` (its prerequisites). Trusted edges only
        by default, so an unconfirmed proposal never drives a learner judgment."""
        out: list[PrerequisiteEdge] = []
        for e in self.edges:
            if e.to_topic_id == topic_id and (e.confirmed or not trusted_only):
                out.append(e)
        return out


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
