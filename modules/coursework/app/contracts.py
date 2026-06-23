"""Pydantic mirrors of the evaluation contract (contracts/src/evaluation/index.ts).

A faithful port of the Zod schemas the evaluation engine produces. Two
non-negotiables are encoded STRUCTURALLY here, exactly as in the contract:

  - a non-high confidence band MUST set ``needs_human_review`` (the engine never
    stands alone on a middle/low band),
  - a consequential mark cannot be ``final`` without ``human_confirmed`` (the
    PERMISSION LADDER: GRADING needs explicit human approval).

The handwriting rule rides on every result: scan/handwriting quality NEVER
reduces a mark — illegible content sets ``needs_human_review``, it does not
penalise. ``never_penalize_handwriting`` is a literal ``True`` carried on the
wire so the rule travels with the result, not just in docs.

Nothing here carries PII. Question/submission refs are opaque ontology/record
tokens.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# The three evaluation modes (align with the event-layer ScoreMode).
# ---------------------------------------------------------------------------
class EvaluationMode(str, Enum):
    """The three modes. ``value`` maps onto the event ScoreMode wire string."""

    POST_SUBMISSION = "post_submission"
    SCANNED_HANDWRITING = "scanned_handwriting"
    PREVENTIVE_BEFORE_SUBMISSION = "preventive_before_submission"


EVALUATION_MODE_DOCS: dict[EvaluationMode, str] = {
    EvaluationMode.POST_SUBMISSION: (
        "The learner has submitted finished work; the engine evaluates it. "
        "Consequential marks here are human-final."
    ),
    EvaluationMode.SCANNED_HANDWRITING: (
        "Evaluates scanned or photographed handwritten work. Scan/handwriting "
        "quality NEVER lowers a mark; illegible content flags needs_human_review."
    ),
    EvaluationMode.PREVENTIVE_BEFORE_SUBMISSION: (
        "Runs before the learner submits, so they can correct mistakes "
        "themselves. This is helping, not grading — it never produces a "
        "consequential mark."
    ),
}

# Map the evaluation mode onto the event-layer ScoreMode string.
_MODE_TO_SCORE_MODE: dict[EvaluationMode, str] = {
    EvaluationMode.POST_SUBMISSION: "post-submission",
    EvaluationMode.SCANNED_HANDWRITING: "scanned-handwriting",
    EvaluationMode.PREVENTIVE_BEFORE_SUBMISSION: "preventive-before-submission",
}


def score_mode_for(mode: EvaluationMode) -> str:
    """The event ScoreMode wire string for an evaluation mode."""
    return _MODE_TO_SCORE_MODE[mode]


# ---------------------------------------------------------------------------
# Answer state + confidence band.
# ---------------------------------------------------------------------------
class AnswerState(str, Enum):
    """How a single response landed. RESPONSE TYPE drives the gap response:

      - incomplete    -> procedural/speed, the learner stopped short,
      - misunderstood -> conceptual, the mental model is wrong.
    """

    CORRECT = "correct"
    INCOMPLETE = "incomplete"
    MISUNDERSTOOD = "misunderstood"


class EvaluationConfidenceBand(str, Enum):
    """Confidence on a single response evaluation. Anything but ``high`` — or any
    consequential mark — routes to human review before it is final."""

    HIGH = "high"
    MIDDLE = "middle"
    LOW = "low"


# The event-layer ScoreRecordedPayload uses low/medium/high. The evaluation
# contract uses low/middle/high. Map at the boundary.
_BAND_TO_EVENT_BAND: dict[EvaluationConfidenceBand, str] = {
    EvaluationConfidenceBand.HIGH: "high",
    EvaluationConfidenceBand.MIDDLE: "medium",
    EvaluationConfidenceBand.LOW: "low",
}


def event_confidence_band_for(band: EvaluationConfidenceBand) -> str:
    """The event ScoreRecordedPayload confidence_band for an evaluation band."""
    return _BAND_TO_EVENT_BAND[band]


# ---------------------------------------------------------------------------
# Rubric criterion + score.
# ---------------------------------------------------------------------------
class RubricCriterion(_Model):
    criterion_id: UUID
    description: str = Field(description="What this criterion assesses, in plain language.")
    max_points: float = Field(ge=0, description="Maximum points this criterion can award.")
    weight: float = Field(default=1.0, ge=0, le=1, description="Relative weight within the rubric, in [0,1].")


class RubricScore(_Model):
    criterion_id: UUID
    points_awarded: float = Field(ge=0)
    max_points: float = Field(ge=0)
    note: str | None = Field(default=None, description="Brief, plain-language justification for this criterion's score.")

    @model_validator(mode="after")
    def _award_within_max(self) -> "RubricScore":
        if self.points_awarded > self.max_points:
            raise ValueError("points_awarded cannot exceed max_points.")
        return self


# ---------------------------------------------------------------------------
# The per-response evaluation result.
# ---------------------------------------------------------------------------
class ResponseEvaluation(_Model):
    """The per-response result. Carries the never-penalize-handwriting rule on
    the wire and enforces the non-high-band review rule structurally."""

    question_ref: UUID = Field(description="Ontology question node this response answers.")
    mode: EvaluationMode
    answer_state: AnswerState
    rubric_score: list[RubricScore] = Field(
        default_factory=list,
        description="Per-criterion breakdown. Empty for a purely correct/incorrect item.",
    )
    confidence_band: EvaluationConfidenceBand
    needs_human_review: bool = Field(
        description="True when the engine is not confident enough to stand alone — low/middle band, ambiguous, or illegible."
    )
    never_penalize_handwriting: bool = Field(
        default=True,
        description="Structural reminder: handwriting/scan quality must never reduce the mark. Illegible work sets needs_human_review.",
    )
    rationale: str = Field(description="Plain-language why-this-result, for explainability and human review.")

    @model_validator(mode="after")
    def _structural_rules(self) -> "ResponseEvaluation":
        # The handwriting rule is a literal True on the wire — never flips.
        if self.never_penalize_handwriting is not True:
            raise ValueError("never_penalize_handwriting must be true on every result.")
        # A non-high confidence band must route to human review.
        if self.confidence_band is not EvaluationConfidenceBand.HIGH and not self.needs_human_review:
            raise ValueError("A non-high confidence band must set needs_human_review true.")
        return self

    @property
    def normalized_score(self) -> float:
        """The rubric breakdown collapsed to a single [0,1] score.

        Weighted by each criterion's max_points (the weight of a criterion is its
        share of the total points). An empty rubric falls back to the answer
        state: correct -> 1.0, otherwise 0.0. This is the ENGINE-RECOMMENDED
        number only; it is never final on a consequential mark.
        """
        if not self.rubric_score:
            return 1.0 if self.answer_state is AnswerState.CORRECT else 0.0
        total_max = sum(rs.max_points for rs in self.rubric_score)
        if total_max <= 0:
            return 1.0 if self.answer_state is AnswerState.CORRECT else 0.0
        awarded = sum(rs.points_awarded for rs in self.rubric_score)
        return max(0.0, min(1.0, awarded / total_max))


# ---------------------------------------------------------------------------
# The human-final marking gate (PERMISSION LADDER).
# ---------------------------------------------------------------------------
class MarkingGate(_Model):
    """A consequential mark is not final until a human confirms it. The engine
    produces the recommended state; ``human_confirmed`` flips only on explicit
    human action, and ``final`` is derived."""

    submission_ref: UUID
    consequential: bool = Field(
        description="True when this mark affects a grade/record/report — always human-final."
    )
    engine_recommended_score: float = Field(ge=0, le=1, description="The engine's recommended normalized score in [0,1].")
    engine_confidence_band: EvaluationConfidenceBand
    human_confirmed: bool = Field(description="True only once a human marker has explicitly confirmed or adjusted the mark.")
    confirmed_by: UUID | None = Field(default=None, description="Opaque ref to the human who confirmed.")
    adjusted_score: float | None = Field(default=None, ge=0, le=1, description="The human's adjusted score, when changed.")
    final: bool = Field(description="Derived: a consequential mark is final only when human_confirmed is true.")

    @model_validator(mode="after")
    def _ladder_rules(self) -> "MarkingGate":
        if self.consequential and self.final and not self.human_confirmed:
            raise ValueError("A consequential mark cannot be final without human_confirmed.")
        if self.human_confirmed and self.confirmed_by is None:
            raise ValueError("human_confirmed requires confirmed_by.")
        return self

    @property
    def effective_score(self) -> float:
        """The score that stands: the human's adjustment if confirmed, else the
        engine recommendation."""
        if self.human_confirmed and self.adjusted_score is not None:
            return self.adjusted_score
        return self.engine_recommended_score
