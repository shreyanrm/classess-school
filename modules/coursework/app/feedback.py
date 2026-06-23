"""Preventive feedback — graduated hints, re-grade requests, reflection (B6, domain 11).

This deepens the EVALUATION engine's Mode 3 (preventive-before-submission) and the
SELF-CORRECTION interactions the dossier names but the engine itself does not yet
produce. Three care-ful, human-centred pieces, each pure and import-safe:

  1. The GRADUATED-HINT LADDER (Mode 3, the dossier line: "the student shows work
     to the camera and gets graduated hints to fix it themselves; never the final
     answer, never forced"). A learner who is stuck is offered hints that escalate
     one rung at a time — orient -> strategy -> next-step -> check-your-working —
     and the ladder STRUCTURALLY refuses to ever hand over the final answer. Hints
     are PULLED by the learner (never forced): the ladder advances only when the
     learner asks for the next one.

  2. The "I THINK I'M RIGHT" RE-GRADE REQUEST (the dossier's d11 self-correction /
     re-grade interaction). When a learner disputes an engine reading, this builds
     a neutral re-grade request that ROUTES TO A HUMAN — it never changes a mark
     itself. A disagreement is a SIGNAL the marker reviews, never a verdict.

  3. CONFIDENCE CHECK-IN + REFLECTION PROMPT. Before or after an attempt, the
     learner is invited (voluntarily) to say how confident they feel and to
     reflect; a large gap between stated confidence and the engine reading is a
     metacognitive SIGNAL for the learner and the teacher — never a penalty.

Non-negotiables encoded here (not just documented):
  - NEVER THE FINAL ANSWER. ``GraduatedHint`` carries ``reveals_answer`` which is
    a literal False, and ``HintLadder`` refuses to mint a rung that would reveal
    the answer. Preventive help teaches; it never solves for the learner.
  - NEVER FORCED. Hints are advanced only on an explicit learner request; the
    ladder tracks how many were pulled, and a learner may stop at any rung.
  - HUMAN-FINAL / RECOMMEND rung. A re-grade request ``requires_approval``; it
    changes no mark. A confidence/reflection read is a SIGNAL, never a mark.
  - NO PII. Learners are opaque ``canonical_uuid`` refs; nothing here carries a
    name, and a hint never echoes the learner's raw answer back.

Pure: no I/O, no network, no provider call. Import-safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4

from .contracts import AnswerState, EvaluationConfidenceBand


# ---------------------------------------------------------------------------
# 1. The graduated-hint ladder (Mode 3) — never the final answer, never forced.
# ---------------------------------------------------------------------------
class HintTier(int, Enum):
    """The rungs of the graduated-hint ladder, in escalating support order. Each
    rung gives a little MORE scaffolding than the last, but none reaches the
    answer — the last rung points the learner at their OWN working to check."""

    ORIENT = 1  # name what the question is really asking (gentlest nudge)
    STRATEGY = 2  # suggest an approach / which idea to use
    NEXT_STEP = 3  # the immediate next move, not the result
    CHECK_WORKING = 4  # invite the learner to re-check their own working

    @property
    def label(self) -> str:
        return {
            HintTier.ORIENT: "orient",
            HintTier.STRATEGY: "strategy",
            HintTier.NEXT_STEP: "next_step",
            HintTier.CHECK_WORKING: "check_working",
        }[self]


# The most support the ladder will ever give. It STOPS one rung short of the
# answer by design — there is no "reveal" tier.
MAX_HINT_TIER = HintTier.CHECK_WORKING


@dataclass(frozen=True)
class GraduatedHint:
    """One hint rung. ``reveals_answer`` is a literal False carried on the wire so
    the never-the-final-answer rule travels with the hint, not just in docs."""

    tier: HintTier
    text: str
    reveals_answer: bool = False
    hint_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        # Structural guard: a hint can never be minted as one that reveals the
        # answer. Preventive help teaches; it never solves for the learner.
        if self.reveals_answer is not False:
            raise ValueError("a graduated hint must never reveal the final answer (reveals_answer must be False).")

    @property
    def rung(self) -> str:
        """Permission-ladder framing: a hint is RECOMMEND-grade help offered to the
        learner — never a mark, never forced."""
        return "recommend"


# Generic, board-agnostic hint text per tier. ``answer_state`` lets the strategy
# rung lean toward the RESPONSE TYPE (procedural vs conceptual) the way the gap
# engine distinguishes incomplete from misunderstood — without ever revealing the
# answer. Topic-specific wording (from a live provider) plugs in upstream; with no
# provider these neutral, never-revealing prompts are used.
def _hint_text(tier: HintTier, answer_state: AnswerState | None) -> str:
    if tier is HintTier.ORIENT:
        return "Re-read the question and say, in your own words, what it is actually asking you to find."
    if tier is HintTier.STRATEGY:
        if answer_state is AnswerState.MISUNDERSTOOD:
            return "Think about which idea or rule this question is really about — does your approach match that idea?"
        if answer_state is AnswerState.INCOMPLETE:
            return "You've started well. Which method did you choose, and is there a step you haven't finished yet?"
        return "Which method or idea fits this kind of question? Pick the approach before you compute."
    if tier is HintTier.NEXT_STEP:
        return "What is the very next step from where you are now? Do just that one step — don't jump to the result."
    # CHECK_WORKING — the furthest the ladder goes: re-check your OWN working.
    return "Go back over your working line by line and check each step. Where does it stop feeling right?"


@dataclass(frozen=True)
class HintLadder:
    """A learner's progress up the graduated-hint ladder for one response.

    Hints are PULLED, not pushed: ``next_hint`` returns the next rung only when the
    learner asks, and ``pulled`` records how many they chose to take. The ladder
    never auto-advances and never goes past ``CHECK_WORKING`` — there is no rung
    that reveals the answer.
    """

    response_ref: UUID
    answer_state: AnswerState | None = None
    pulled: int = 0

    @property
    def rung(self) -> str:
        return "recommend"

    @property
    def exhausted(self) -> bool:
        """True once every supportive rung has been offered. Even exhausted, the
        ladder has not revealed the answer — it has only invited self-checking."""
        return self.pulled >= MAX_HINT_TIER.value

    @property
    def reveals_answer(self) -> bool:
        """A literal, structural promise: the ladder NEVER reveals the answer."""
        return False

    def next_hint(self) -> tuple["HintLadder", GraduatedHint | None]:
        """Pull the next hint (an explicit learner act — never forced).

        Returns the advanced ladder and the new hint, or the unchanged ladder and
        ``None`` once the supportive rungs are exhausted. The final rung points the
        learner back at their own working; there is never a rung beyond it that
        hands over the answer.
        """
        if self.exhausted:
            return self, None
        tier = HintTier(self.pulled + 1)
        hint = GraduatedHint(tier=tier, text=_hint_text(tier, self.answer_state))
        advanced = HintLadder(response_ref=self.response_ref, answer_state=self.answer_state, pulled=self.pulled + 1)
        return advanced, hint


def start_hint_ladder(*, response_ref: UUID, answer_state: AnswerState | None = None) -> HintLadder:
    """Begin a graduated-hint ladder for a stuck learner in preventive mode.

    Nothing is offered yet — the learner pulls the first hint when they want it.
    ``answer_state`` (when known from a preventive evaluation) lets the strategy
    rung lean toward procedural vs conceptual help, never toward the answer.
    """
    return HintLadder(response_ref=response_ref, answer_state=answer_state, pulled=0)


# ---------------------------------------------------------------------------
# 2. "I think I'm right" — a learner-initiated RE-GRADE REQUEST (human-final).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RegradeRequest:
    """A learner's "I think I'm right" challenge to an engine reading.

    It NEVER changes a mark. It is a PREPARE/RECOMMEND-rung request routed to a
    human marker, who reviews and decides. Carries only opaque refs and a neutral
    learner reason — no PII. ``requires_approval`` is true: a re-grade is a
    consequential change a human owns."""

    submission_ref: UUID
    question_ref: UUID
    requested_by: UUID  # opaque canonical_uuid of the learner — never PII
    engine_answer_state: AnswerState
    engine_confidence_band: EvaluationConfidenceBand
    learner_reason: str
    rationale: str
    request_id: UUID = field(default_factory=uuid4)

    @property
    def rung(self) -> str:
        return "recommend"

    @property
    def requires_approval(self) -> bool:
        """A re-grade is human-final — it requires explicit marker approval and
        never auto-changes a mark."""
        return True


def request_regrade(
    *,
    submission_ref: UUID,
    question_ref: UUID,
    requested_by: UUID,
    engine_answer_state: AnswerState,
    engine_confidence_band: EvaluationConfidenceBand,
    learner_reason: str = "",
) -> RegradeRequest:
    """Build an "I think I'm right" re-grade request for a human to review.

    This changes NO mark. It captures the learner's disagreement neutrally and
    routes it to a marker — and it is especially apt when the engine itself was not
    fully confident (a non-high band), where a learner challenge is exactly the
    signal a human should see. The marker confirms or adjusts via the evaluation
    engine's ``confirm_mark``; this module never touches the mark.
    """
    low_conf = engine_confidence_band is not EvaluationConfidenceBand.HIGH
    rationale = (
        "Learner believes their answer is right and has asked for a human re-grade. "
        + (
            "The engine was not fully confident here (non-high band), so a human look is especially warranted. "
            if low_conf
            else "The engine read this with high confidence; a human still reviews the challenge. "
        )
        + "This request changes no mark — a marker reviews and decides."
    )
    return RegradeRequest(
        submission_ref=submission_ref,
        question_ref=question_ref,
        requested_by=requested_by,
        engine_answer_state=engine_answer_state,
        engine_confidence_band=engine_confidence_band,
        learner_reason=learner_reason.strip(),
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# 3. Confidence check-in + reflection — a metacognitive SIGNAL, never a mark.
# ---------------------------------------------------------------------------
class StatedConfidence(str, Enum):
    """How confident the learner says they feel — a voluntary self-report."""

    NOT_SURE = "not_sure"
    SOMEWHAT = "somewhat"
    CONFIDENT = "confident"


_STATED_CONFIDENCE_LEVEL: dict[StatedConfidence, float] = {
    StatedConfidence.NOT_SURE: 0.2,
    StatedConfidence.SOMEWHAT: 0.55,
    StatedConfidence.CONFIDENT: 0.9,
}

_ENGINE_BAND_LEVEL: dict[EvaluationConfidenceBand, float] = {
    EvaluationConfidenceBand.LOW: 0.2,
    EvaluationConfidenceBand.MIDDLE: 0.55,
    EvaluationConfidenceBand.HIGH: 0.9,
}

# A gap this large between stated confidence and the engine reading is a
# calibration SIGNAL worth surfacing (e.g. "confident but the work looks off", or
# "unsure but actually correct"). A signal, never a penalty.
_CALIBRATION_GAP_THRESHOLD = 0.4


@dataclass(frozen=True)
class ConfidenceCheckIn:
    """A learner's voluntary confidence self-report against an engine reading.

    The CALIBRATION gap (stated vs engine) is a metacognitive signal for the
    learner and the teacher — over-confidence on shaky work, or under-confidence on
    sound work, both worth a gentle reflection. It is NEVER a mark and NEVER a
    penalty."""

    response_ref: UUID
    stated: StatedConfidence
    engine_band: EvaluationConfidenceBand
    calibration_gap: float
    miscalibrated: bool
    rationale: str

    @property
    def rung(self) -> str:
        return "recommend"


def confidence_check_in(
    *,
    response_ref: UUID,
    stated: StatedConfidence,
    engine_band: EvaluationConfidenceBand,
    gap_threshold: float = _CALIBRATION_GAP_THRESHOLD,
) -> ConfidenceCheckIn:
    """Compare a learner's stated confidence to the engine reading.

    A large gap is flagged as ``miscalibrated`` — a signal to invite reflection,
    never a penalty. The direction (over- or under-confident) is named in the
    rationale so the feedback is specific and kind.
    """
    stated_level = _STATED_CONFIDENCE_LEVEL[stated]
    engine_level = _ENGINE_BAND_LEVEL[engine_band]
    gap = abs(stated_level - engine_level)
    miscalibrated = gap >= gap_threshold
    if not miscalibrated:
        rationale = "Your sense of how this went lines up with the work — well calibrated."
    elif stated_level > engine_level:
        rationale = (
            "You felt more sure than the work suggests. That's worth a second look — "
            "going back over it now can catch something before it counts. No penalty for the gap."
        )
    else:
        rationale = (
            "You felt less sure than the work suggests — it looks stronger than you think. "
            "Trust your working a little more. No penalty for the gap."
        )
    return ConfidenceCheckIn(
        response_ref=response_ref,
        stated=stated,
        engine_band=engine_band,
        calibration_gap=gap,
        miscalibrated=miscalibrated,
        rationale=rationale,
    )


@dataclass(frozen=True)
class ReflectionPrompt:
    """A gentle, open reflection question offered to the learner after an attempt.

    Voluntary and never a mark. The prompt is shaped by HOW the response landed
    (correct / incomplete / misunderstood) so the reflection is relevant, and it
    invites self-correction rather than asserting a verdict."""

    response_ref: UUID
    answer_state: AnswerState
    prompt: str

    @property
    def rung(self) -> str:
        return "recommend"


def reflection_prompt(*, response_ref: UUID, answer_state: AnswerState) -> ReflectionPrompt:
    """Build a reflection prompt shaped by how the response landed.

    Correct -> consolidate the reasoning; incomplete -> notice the missing step;
    misunderstood -> revisit the underlying idea. Always an invitation, never a
    judgement; it feeds the self-correction interaction, not a mark."""
    if answer_state is AnswerState.CORRECT:
        prompt = "Nice work. In a sentence, what was the key idea that made this one work? Naming it helps it stick."
    elif answer_state is AnswerState.INCOMPLETE:
        prompt = "You were on the way. Where did you stop, and what would the next step have been? No marks ride on this."
    else:  # MISUNDERSTOOD
        prompt = (
            "Let's look at the idea behind this one. What did you think it was asking, "
            "and what might it actually be about? Take your time — this isn't graded."
        )
    return ReflectionPrompt(response_ref=response_ref, answer_state=answer_state, prompt=prompt)
