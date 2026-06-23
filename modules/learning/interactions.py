"""The four named build-interaction types as first-class objects (d12).

"Build, don't watch": concepts are derived, solved, or assembled by the learner,
never narrated at them. The universal loop is POSE -> STRUGGLE -> REVEAL (see
:mod:`learning.learn`). This module gives the four named interaction types from
the document their own first-class contract + verification:

  1. PREDICT-THEN-CHECK simulation — the learner commits to a prediction BEFORE
     running the check; the system runs the deterministic check and confronts the
     learner with the gap between prediction and outcome. The commitment must come
     first: a prediction recorded after the result is seen is not a prediction.
  2. ASSEMBLE-THE-PROOF — the learner orders a shuffled set of steps into a valid
     chain. Verification is structural: every step's premises must already be
     established (axioms or earlier-placed steps) before it is used, and the final
     step must reach the goal. The learner builds the argument; we check the build.
  3. FILL-THE-MISSING-STEP — a derivation is shown with one (or more) steps blank;
     the learner supplies the missing step. Verification checks the supplied step
     against the deterministically-known answer for that slot, never by lecturing
     the rest of the derivation.
  4. TEACH-IT-BACK-TO-THE-COMPANION — the learner explains the idea back; the
     companion plays a naive learner and the explanation is checked for COVERAGE
     of the key points (the load-bearing ideas that must appear) rather than for
     prose quality. Gaps in coverage become the companion's follow-up question —
     posed, never corrected.

Each interaction shares one contract:

  - it POSES (an interaction is a task, not a narration);
  - it VERIFIES deterministically (the check is re-runnable, never fabricated);
  - it produces an attempt EVIDENCE payload via :mod:`learning.events`, carrying
    the keystone independent-vs-supported flag — an interaction completed with a
    revealed scaffold is SUPPORTED, an unaided build is INDEPENDENT.

Pure and import-safe: stdlib only; the event builder is imported lazily. Carries
only opaque ontology ids — never PII (INVARIANT 1 + 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


class InteractionType(str, Enum):
    """The four named build-interaction types. Labels, not free text, so a surface
    can switch on them and a test can assert exhaustiveness."""

    PREDICT_THEN_CHECK = "predict_then_check"
    ASSEMBLE_THE_PROOF = "assemble_the_proof"
    FILL_THE_MISSING_STEP = "fill_the_missing_step"
    TEACH_IT_BACK = "teach_it_back"


# The four, as an explicit tuple so callers and tests can iterate the full set.
ALL_INTERACTION_TYPES: tuple[InteractionType, ...] = (
    InteractionType.PREDICT_THEN_CHECK,
    InteractionType.ASSEMBLE_THE_PROOF,
    InteractionType.FILL_THE_MISSING_STEP,
    InteractionType.TEACH_IT_BACK,
)


@dataclass(frozen=True)
class InteractionVerdict:
    """The verification result for one build-interaction attempt.

    ``correct`` is the deterministic pass/fail; ``score`` is partial credit in
    [0,1]; ``feedback`` is a POSED follow-up or a plain confirmation — never a
    lecture; ``detail`` carries the explainable, PII-free breakdown the surface
    and audit can show.
    """

    interaction: InteractionType
    correct: bool
    score: float
    feedback: str
    detail: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared evidence emission — every interaction yields an attempt payload.
# ---------------------------------------------------------------------------
# Difficulty each interaction is treated as carrying by default; an interaction is
# a real cognitive task, never trivially easy.
_DEFAULT_DIFFICULTY: dict[InteractionType, float] = {
    InteractionType.PREDICT_THEN_CHECK: 0.5,
    InteractionType.ASSEMBLE_THE_PROOF: 0.65,
    InteractionType.FILL_THE_MISSING_STEP: 0.55,
    InteractionType.TEACH_IT_BACK: 0.6,
}


def build_interaction_evidence(
    *,
    interaction: InteractionType,
    topic_id: str,
    verdict: InteractionVerdict,
    used_help: bool,
    time_taken_ms: int,
    question_id: str | None = None,
    difficulty: float | None = None,
    attempt_number: int = 1,
) -> dict[str, Any]:
    """Turn an interaction verdict into an attempt-evidence payload.

    The keystone independent-vs-supported flag is set from ``used_help``: a build
    completed with a revealed scaffold is SUPPORTED (assistance level 'Hint');
    an unaided build is the Independent rung. The payload is the canonical
    ``attempt.recorded`` shape so an interaction contributes EVIDENCE exactly like
    any other attempt — never a bespoke "completed" tick.
    """
    from . import events as _events  # lazy: keep this module import-safe

    assistance_level = "Hint" if used_help else "Independent"
    return _events.build_attempt_payload(
        topic_id=topic_id,
        assistance_level=assistance_level,
        correct=verdict.correct,
        difficulty=difficulty if difficulty is not None else _DEFAULT_DIFFICULTY[interaction],
        time_taken_ms=max(0, int(time_taken_ms)),
        score=verdict.score,
        question_id=question_id,
        attempt_number=attempt_number,
    )


# ===========================================================================
# 1 · PREDICT-THEN-CHECK simulation
# ===========================================================================
@dataclass
class PredictThenCheck:
    """A predict-then-check simulation.

    Contract: the learner must COMMIT a prediction before the check runs. The
    deterministic check (a re-runnable claim) is then evaluated and the learner is
    shown the gap between what they predicted and what happened. A prediction made
    after the outcome is visible is rejected — the whole value is in committing
    first.
    """

    topic_id: str
    prompt: str                       # the scenario posed to the learner
    check_expression: str             # the deterministic claim, e.g. "8 * 0.5"
    actual_outcome: float             # the deterministically-true result
    tolerance: float = 1e-6
    question_id: str | None = None

    _prediction: float | None = field(default=None, init=False)
    _committed: bool = field(default=False, init=False)
    _checked: bool = field(default=False, init=False)

    @property
    def type(self) -> InteractionType:
        return InteractionType.PREDICT_THEN_CHECK

    def commit_prediction(self, value: float) -> None:
        """Record the learner's prediction. MUST be called before :meth:`check`;
        calling it after the check has run raises — a post-hoc prediction is not a
        prediction."""
        if self._checked:
            raise RuntimeError(
                "cannot record a prediction after the check has run — the "
                "prediction must be committed first."
            )
        self._prediction = float(value)
        self._committed = True

    def check(self) -> InteractionVerdict:
        """Run the deterministic check and confront the learner with the gap.

        Raises if no prediction was committed first (the anti-explain-first guard
        for this interaction)."""
        if not self._committed or self._prediction is None:
            raise RuntimeError(
                "a prediction must be committed before the check is run."
            )
        self._checked = True
        gap = abs(self._prediction - self.actual_outcome)
        correct = gap <= self.tolerance
        if correct:
            feedback = (
                "Your prediction matched what happened — what in the setup made "
                "you confident it would?"
            )
        else:
            feedback = (
                "Your prediction and what actually happened do not match — what "
                "in the setup would change to close that gap?"
            )
        return InteractionVerdict(
            interaction=self.type,
            correct=correct,
            score=1.0 if correct else 0.0,
            feedback=feedback,
            detail={
                "predicted": self._prediction,
                "actual": self.actual_outcome,
                "gap": gap,
                "deterministic_check": {
                    "expression": self.check_expression,
                    "claimed_answer": self.actual_outcome,
                },
            },
        )


# ===========================================================================
# 2 · ASSEMBLE-THE-PROOF
# ===========================================================================
@dataclass(frozen=True)
class ProofStep:
    """One step in a proof/derivation. ``step_id`` is opaque; ``requires`` lists
    the step_ids (or givens) this step depends on; ``establishes`` is what it
    makes available to later steps."""

    step_id: str
    statement: str
    requires: tuple[str, ...] = ()
    establishes: str | None = None


@dataclass
class AssembleTheProof:
    """Assemble a shuffled set of steps into a valid chain.

    Verification is STRUCTURAL, not a string match against a single "right order":
    a placement is valid when every premise the step ``requires`` is already
    established (a given, or an earlier-placed step's ``establishes``), and the
    chain is complete when the ``goal`` has been established. Any valid topological
    order passes — the learner built a sound argument, not memorised one ordering.
    """

    topic_id: str
    prompt: str
    steps: tuple[ProofStep, ...]
    goal: str                          # the statement the proof must reach
    givens: tuple[str, ...] = ()       # premises available from the start
    question_id: str | None = None

    @property
    def type(self) -> InteractionType:
        return InteractionType.ASSEMBLE_THE_PROOF

    def verify(self, ordered_step_ids: Sequence[str]) -> InteractionVerdict:
        """Verify the learner's ordering. Walks the chain, checking each step's
        premises are established before it is used; the first unmet step is
        reported as a posed question, not a correction."""
        by_id = {s.step_id: s for s in self.steps}
        established: set[str] = set(self.givens)
        placed = 0
        first_problem: str | None = None
        for sid in ordered_step_ids:
            step = by_id.get(sid)
            if step is None:
                first_problem = sid
                break
            unmet = [r for r in step.requires if r not in established]
            if unmet:
                first_problem = sid
                break
            placed += 1
            if step.establishes:
                established.add(step.establishes)
        reached_goal = self.goal in established
        total = len(self.steps)
        score = round(placed / total, 3) if total else 0.0
        correct = reached_goal and first_problem is None and placed == total
        if correct:
            feedback = "The chain holds end to end — which step was the one the whole argument turned on?"
        elif first_problem is not None:
            bad = by_id.get(first_problem)
            stmt = bad.statement if bad else "that step"
            feedback = (
                f"At this point the argument uses something not yet established — "
                f"what has to come before \"{stmt}\" for it to follow?"
            )
        else:
            feedback = "The steps are each sound, but the chain has not reached the goal yet — what is still missing to get there?"
        return InteractionVerdict(
            interaction=self.type,
            correct=correct,
            score=score,
            feedback=feedback,
            detail={
                "placed": placed,
                "total": total,
                "reached_goal": reached_goal,
                "first_unmet_step": first_problem,
            },
        )


# ===========================================================================
# 3 · FILL-THE-MISSING-STEP
# ===========================================================================
@dataclass(frozen=True)
class DerivationSlot:
    """One blanked step in a derivation. ``answer`` is the deterministically-known
    content for the slot; ``acceptable`` lists equivalent acceptable forms."""

    slot_id: str
    answer: str
    acceptable: tuple[str, ...] = ()


@dataclass
class FillTheMissingStep:
    """A derivation shown with one or more steps blanked for the learner to fill.

    Verification compares each supplied step against the deterministically-known
    answer for that slot (normalised, with acceptable equivalents). It NEVER
    lectures the rest of the derivation; an unfilled or wrong slot becomes a posed
    nudge about that slot only.
    """

    topic_id: str
    prompt: str
    visible_steps: tuple[str, ...]     # the steps shown around the blanks
    slots: tuple[DerivationSlot, ...]  # the blanks to fill
    question_id: str | None = None

    @property
    def type(self) -> InteractionType:
        return InteractionType.FILL_THE_MISSING_STEP

    @staticmethod
    def _norm(text: str) -> str:
        return " ".join(str(text).strip().lower().replace(" ", "").split())

    def verify(self, filled: Mapping[str, str]) -> InteractionVerdict:
        """Verify the learner's filled slots against the known answers."""
        if not self.slots:
            raise ValueError("a fill-the-missing-step item must have at least one slot.")
        correct_slots = 0
        wrong: list[str] = []
        for slot in self.slots:
            supplied = filled.get(slot.slot_id)
            if supplied is None:
                wrong.append(slot.slot_id)
                continue
            candidates = {self._norm(slot.answer)} | {self._norm(a) for a in slot.acceptable}
            if self._norm(supplied) in candidates:
                correct_slots += 1
            else:
                wrong.append(slot.slot_id)
        total = len(self.slots)
        score = round(correct_slots / total, 3)
        correct = correct_slots == total
        if correct:
            feedback = "Every missing step is in place — can you say in one line why that step had to be there?"
        else:
            feedback = (
                "One of the missing steps does not yet follow from the line above "
                "it — what has to be true at that point for the next line to hold?"
            )
        return InteractionVerdict(
            interaction=self.type,
            correct=correct,
            score=score,
            feedback=feedback,
            detail={"correct_slots": correct_slots, "total": total, "unsolved": tuple(wrong)},
        )


# ===========================================================================
# 4 · TEACH-IT-BACK-TO-THE-COMPANION
# ===========================================================================
@dataclass(frozen=True)
class KeyPoint:
    """One load-bearing idea the learner's explanation must cover. ``keywords``
    are any-of surface forms that signal the idea is present (deterministic
    coverage check; a live model could later propose richer matching through the
    verified ai-fabric path)."""

    point_id: str
    description: str
    keywords: tuple[str, ...]


@dataclass
class TeachItBack:
    """Teach-it-back: the learner explains the idea; the companion plays a naive
    learner and checks COVERAGE of the key points.

    Verification is coverage-based — does the explanation touch each load-bearing
    idea? — not a judgment of prose quality. An uncovered key point becomes the
    companion's follow-up QUESTION (posed in the naive-learner voice), never a
    correction. ``pass_threshold`` is the share of key points that must be covered
    to count as a correct teach-back.
    """

    topic_id: str
    prompt: str
    key_points: tuple[KeyPoint, ...]
    pass_threshold: float = 0.7
    question_id: str | None = None

    @property
    def type(self) -> InteractionType:
        return InteractionType.TEACH_IT_BACK

    def verify(self, explanation: str) -> InteractionVerdict:
        """Check the explanation for coverage of the key points. Returns a verdict
        whose feedback is the companion's posed follow-up about the FIRST uncovered
        idea, or a confirmation when coverage is sufficient."""
        if not self.key_points:
            raise ValueError("a teach-it-back item must declare at least one key point.")
        low = explanation.lower()
        covered: list[str] = []
        missing: list[KeyPoint] = []
        for kp in self.key_points:
            if any(kw.lower() in low for kw in kp.keywords):
                covered.append(kp.point_id)
            else:
                missing.append(kp)
        total = len(self.key_points)
        score = round(len(covered) / total, 3)
        correct = score >= self.pass_threshold
        if missing:
            # The companion, as a naive learner, asks about the first gap. Posed,
            # never a correction — no "you forgot..." phrasing.
            gap = missing[0]
            feedback = (
                f"I think I follow, but I am still not sure about one thing — "
                f"can you explain {gap.description}?"
            )
        else:
            feedback = "That made sense to me — now, where might this idea break down?"
        return InteractionVerdict(
            interaction=self.type,
            correct=correct,
            score=score,
            feedback=feedback,
            detail={
                "covered": tuple(covered),
                "missing": tuple(m.point_id for m in missing),
                "total": total,
            },
        )

    def follow_up(self, explanation: str) -> str | None:
        """The companion's next posed question (or None when coverage is full).
        A thin convenience over :meth:`verify` for a surface that only wants the
        next prompt."""
        verdict = self.verify(explanation)
        missing = verdict.detail.get("missing") or ()
        return verdict.feedback if missing else None
