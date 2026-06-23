"""The "I think I am right" re-grade path + confidence check-ins + reflection (d11/d12).

"Confidence check-ins, reflection prompts, and an 'I think I'm right' re-grade
path build self-assessment." The platform's deepest job is to make a learner a
better judge of their own understanding. This module is the bounded, deterministic
logic behind three self-regulation surfaces:

  1. CONFIDENCE CHECK-IN — before (and after) an answer, the learner states how
     sure they are. Pairing confidence with correctness exposes CALIBRATION: a
     confident wrong answer (a misconception held firmly) is a different teaching
     moment from an unsure right answer (knowledge not yet trusted). The check-in
     is a SIGNAL, never a grade.
  2. THE "I THINK I AM RIGHT" RE-GRADE / DISPUTE PATH — when a learner believes an
     auto-grade is wrong, they can dispute it with their reasoning. This module
     PREPARES a re-grade request: it re-runs the deterministic check where one
     exists (a symbolic/arithmetic answer can be re-verified objectively), and
     otherwise routes the dispute to a human with the evidence attached. It NEVER
     auto-overturns a consequential mark — overturning a published/graded mark is
     a consequential action, so the result is ``requires_approval`` and the human
     is final (PERMISSION LADDER + human-is-final invariants).
  3. REFLECTION PROMPTS — after an attempt, a posed reflection question chosen to
     fit the outcome + calibration (a confident-wrong outcome gets a different
     prompt from an unsure-right one). Posed, never a correction.

Pure, deterministic, import-safe, offline. Carries only opaque ids — never PII.
A re-grade request is a PREPARED action object; the caller routes it through the
approval/permission tier. Nothing here sends, publishes, or overturns anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Confidence check-ins + calibration.
# ---------------------------------------------------------------------------
class Confidence(str, Enum):
    """A learner's stated confidence. A coarse, honest scale — not a number to
    grade, a signal to teach against."""

    GUESSING = "guessing"
    UNSURE = "unsure"
    FAIRLY_SURE = "fairly_sure"
    CERTAIN = "certain"


_CONFIDENCE_LEVEL: dict[Confidence, float] = {
    Confidence.GUESSING: 0.1,
    Confidence.UNSURE: 0.4,
    Confidence.FAIRLY_SURE: 0.7,
    Confidence.CERTAIN: 0.95,
}


class Calibration(str, Enum):
    """The pairing of stated confidence with actual correctness — the teachable
    quadrant."""

    WELL_CALIBRATED = "well_calibrated"      # confident & right, or unsure & wrong
    OVERCONFIDENT = "overconfident"          # confident but wrong (firm misconception)
    UNDERCONFIDENT = "underconfident"        # unsure but right (untrusted knowledge)
    GUESSED_RIGHT = "guessed_right"          # guessing & right (no real evidence)


@dataclass(frozen=True)
class ConfidenceCheckIn:
    """One paired confidence + outcome reading. ``plain_language`` is the only
    learner-facing line — never the raw calibration number (CONFIDENTIALITY)."""

    confidence: Confidence
    correct: bool
    calibration: Calibration
    plain_language: str


def assess_calibration(*, confidence: Confidence, correct: bool) -> ConfidenceCheckIn:
    """Pair confidence with correctness into a calibration reading.

    The two teachable cases are OVERCONFIDENT (certain but wrong — a misconception
    held firmly, the priority for misconception detonation) and UNDERCONFIDENT
    (unsure but right — knowledge the learner does not yet trust, the priority for
    confidence-building practice).
    """
    level = _CONFIDENCE_LEVEL[confidence]
    high = level >= 0.7
    if correct and high:
        cal = Calibration.WELL_CALIBRATED
        plain = "you were sure and you were right — that is well-judged"
    elif correct and confidence is Confidence.GUESSING:
        cal = Calibration.GUESSED_RIGHT
        plain = "right answer, but you were guessing — worth confirming you can do it for sure"
    elif correct and not high:
        cal = Calibration.UNDERCONFIDENT
        plain = "you got it right but were unsure — your understanding is ahead of your confidence"
    elif (not correct) and high:
        cal = Calibration.OVERCONFIDENT
        plain = "you were sure but it did not hold — this is exactly the kind of gap worth looking at closely"
    else:
        cal = Calibration.WELL_CALIBRATED
        plain = "you were unsure and it did not hold — your judgement of that was accurate"
    return ConfidenceCheckIn(
        confidence=confidence, correct=correct, calibration=cal, plain_language=plain
    )


# ---------------------------------------------------------------------------
# Reflection prompts — posed, fitted to outcome + calibration.
# ---------------------------------------------------------------------------
_REFLECTION_BY_CALIBRATION: dict[Calibration, str] = {
    Calibration.WELL_CALIBRATED: (
        "What was the step you were most sure about, and how did you know it was right?"
    ),
    Calibration.OVERCONFIDENT: (
        "You were confident here — what assumption felt obviously true, and how could you test it?"
    ),
    Calibration.UNDERCONFIDENT: (
        "You got this right but were unsure — what would make you trust this next time?"
    ),
    Calibration.GUESSED_RIGHT: (
        "You landed on it by guessing — what would you need to know to be sure rather than lucky?"
    ),
}


def reflection_prompt(check_in: ConfidenceCheckIn) -> str:
    """A posed reflection question fitted to the calibration. Always a question
    (self-assessment is built by asking, not by telling)."""
    prompt = _REFLECTION_BY_CALIBRATION[check_in.calibration]
    # Defensive: a reflection prompt must pose, never assert.
    if "?" not in prompt:
        raise ValueError("a reflection prompt must pose a question.")
    return prompt


# ---------------------------------------------------------------------------
# The "I think I am right" re-grade / dispute path.
# ---------------------------------------------------------------------------
class RegradeRoute(str, Enum):
    """Where a re-grade request is routed."""

    AUTO_VERIFY = "auto_verify"          # a deterministic check can re-settle it
    HUMAN_REVIEW = "human_review"        # subjective; the teacher decides


class RegradeOutcome(str, Enum):
    """The deterministic re-verification outcome (advisory only)."""

    LEARNER_VINDICATED = "learner_vindicated"   # the re-check supports the learner
    ORIGINAL_UPHELD = "original_upheld"          # the re-check supports the grade
    INCONCLUSIVE = "inconclusive"                # no objective check available


@dataclass(frozen=True)
class RegradeDispute:
    """A learner's dispute of an auto-grade. ``learner_reasoning`` is the
    learner's own argument; the optional deterministic ``check`` lets an objective
    answer be re-verified."""

    topic_id: str
    question_id: str | None
    learner_answer: str
    original_marked_correct: bool
    learner_reasoning: str
    # Optional objective re-check: {"expression", "claimed_answer"} or a callable
    # is not accepted (import-safe, no side effects) — only data.
    deterministic_check: Mapping[str, Any] | None = None
    is_consequential: bool = True       # disputing a published/graded mark is consequential


@dataclass(frozen=True)
class RegradeRequest:
    """A PREPARED re-grade request. It is never auto-applied: a consequential mark
    change requires human approval (PERMISSION LADDER; human-is-final).

    ``requires_approval`` is True for any consequential mark; ``advisory_outcome``
    is the deterministic re-check's read (when one exists) to INFORM the human,
    not to overturn on its own. ``provenance`` carries the explainable why +
    evidence (INVARIANT: explainable provenance)."""

    topic_id: str
    question_id: str | None
    route: RegradeRoute
    advisory_outcome: RegradeOutcome
    requires_approval: bool
    learner_reasoning: str
    provenance: str
    prepared_at: str

    @property
    def auto_overturned(self) -> bool:
        """Always False: nothing here overturns a consequential mark automatically."""
        return False


def _to_number(text: Any) -> float | None:
    try:
        return float(str(text).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def prepare_regrade(dispute: RegradeDispute, *, asof: datetime | None = None) -> RegradeRequest:
    """Prepare an "I think I am right" re-grade request.

    Where a deterministic check exists, re-run it and attach the advisory outcome
    (e.g. a symbolic/arithmetic answer can be objectively re-verified). Otherwise
    route to human review. EITHER WAY, a consequential mark change is returned as
    ``requires_approval`` — the human is final; this never overturns a grade.
    """
    asof = asof or datetime.now(timezone.utc)

    route = RegradeRoute.HUMAN_REVIEW
    outcome = RegradeOutcome.INCONCLUSIVE
    why = (
        "This dispute is subjective or has no objective re-check, so it is routed "
        "to the teacher with the learner's reasoning attached."
    )

    check = dispute.deterministic_check
    if check and "claimed_answer" in check:
        route = RegradeRoute.AUTO_VERIFY
        claimed = _to_number(check.get("claimed_answer"))
        learner_val = _to_number(dispute.learner_answer)
        if claimed is not None and learner_val is not None:
            matches = abs(claimed - learner_val) <= float(check.get("tolerance", 1e-6))
            if matches and not dispute.original_marked_correct:
                outcome = RegradeOutcome.LEARNER_VINDICATED
                why = (
                    "The learner's answer matches the deterministic re-check, but it "
                    "was marked wrong — the re-check supports the learner. A human "
                    "must confirm before any consequential mark changes."
                )
            elif not matches and dispute.original_marked_correct is False:
                outcome = RegradeOutcome.ORIGINAL_UPHELD
                why = (
                    "The deterministic re-check does not support the learner's "
                    "answer; the original mark stands pending human confirmation."
                )
            else:
                outcome = RegradeOutcome.ORIGINAL_UPHELD
                why = (
                    "The deterministic re-check agrees with the original mark; it is "
                    "upheld, with the learner's reasoning recorded."
                )
        else:
            outcome = RegradeOutcome.INCONCLUSIVE
            route = RegradeRoute.HUMAN_REVIEW
            why = (
                "The answer could not be re-checked objectively, so the dispute "
                "goes to the teacher with the learner's reasoning."
            )

    requires_approval = bool(dispute.is_consequential)
    return RegradeRequest(
        topic_id=dispute.topic_id,
        question_id=dispute.question_id,
        route=route,
        advisory_outcome=outcome,
        requires_approval=requires_approval,
        learner_reasoning=dispute.learner_reasoning,
        provenance=why,
        prepared_at=asof.isoformat(),
    )
