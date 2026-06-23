"""The evaluation engine — CORE (correctness is existential) (B6).

THREE MODES, one engine. Each produces, per response, a ``ResponseEvaluation``
carrying ``answer_state`` + ``rubric_score`` + ``confidence_band``, and a
``MarkingGate`` for the submission that encodes the human-final rule.

The non-negotiables, all encoded structurally (not just in docs):

  1. PERMISSION LADDER — GRADING is consequential. A consequential mark is only
     ``final`` when a human has confirmed it. A HIGH-confidence engine result may
     be a PROVISIONAL-AUTO recommendation; MIDDLE/LOW must be reviewed before any
     mark stands. The engine holds no authority to finalise.
  2. NEVER PENALISE HANDWRITING — in ``scanned_handwriting`` mode, poor scan or
     illegible handwriting NEVER reduces a mark. It sets ``needs_human_review``;
     the rubric score is left at the legible-content reading or deferred entirely.
  3. PREVENTIVE MODE IS HELPING, NOT GRADING — it produces feedback so the
     learner can fix their work BEFORE submitting; it never produces a
     consequential mark and the marking gate is non-consequential and never final.
  4. NEVER CONFIRM FROM A SINGLE BAD SCORE — the engine emits the per-response
     signal banded by confidence; the learner JUDGMENT is the evidence engine's
     job, and a lone low result is surfaced for review, never as a verdict.

Deterministic scoring where possible (objective items via the rubric + the
ai-fabric symbolic/numeric verifier); the second-model cross-check and any
free-text judgement route through the fabric, which refuses cleanly with no
provider. Confidence banding is explicit and conservative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from .contracts import (
    AnswerState,
    EvaluationConfidenceBand,
    EvaluationMode,
    MarkingGate,
    ResponseEvaluation,
    RubricScore,
)
from .rubric import Rubric, ScoredRubric, score_response


# ---------------------------------------------------------------------------
# AI-fabric verify substrate — consumed lazily, never modified. Used for the
# deterministic math/physics verifier and the confidence gate.
# ---------------------------------------------------------------------------
def _load_verify():
    """Load the ai-fabric verify substrate, sharing papers' robust loader.

    Import-safe: returns None when the substrate is absent, degrading the engine
    to a clearly-flagged review path rather than fabricating a mark.
    """
    from .papers import _load_fabric

    return _load_fabric()


# ---------------------------------------------------------------------------
# Inputs.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ResponseInput:
    """One response to evaluate."""

    question_ref: UUID
    # Objective check: a deterministic expression + the learner's claimed answer.
    expression: str | None = None
    learner_answer: float | None = None
    # Rubric-scored work: a rubric + per-criterion point awards.
    rubric: Rubric | None = None
    awards: dict[UUID, float] | None = None
    award_notes: dict[UUID, str] | None = None
    # Scanned-handwriting signal: OCR legibility/confidence in [0,1], and whether
    # the OCR text was recovered at all. Low legibility flags review, never penalises.
    ocr_confidence: float | None = None
    ocr_text_recovered: bool = True
    # Free-text response (routed to the fabric for a judged read; refuses w/o provider).
    free_text: str | None = None


@dataclass(frozen=True)
class SubmissionInput:
    """A submission to evaluate: the learner, the responses, and whether the
    resulting mark is CONSEQUENTIAL (affects a grade/record/report)."""

    submission_ref: UUID
    scored_subject: UUID  # opaque canonical_uuid of the learner — never PII
    responses: list[ResponseInput]
    consequential: bool = True


# ---------------------------------------------------------------------------
# Results.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EvaluationOutcome:
    """The full evaluation of a submission in one mode."""

    mode: EvaluationMode
    submission_ref: UUID
    scored_subject: UUID
    responses: list[ResponseEvaluation]
    marking_gate: MarkingGate
    # Per-response review reasons, for the human reviewer.
    review_notes: list[str] = field(default_factory=list)

    @property
    def needs_human_review(self) -> bool:
        return any(r.needs_human_review for r in self.responses) or (
            self.marking_gate.consequential and not self.marking_gate.final
        )

    @property
    def recommended_score(self) -> float:
        return self.marking_gate.engine_recommended_score


# Legibility at/below this is "poor scan/handwriting": review, never penalise.
POOR_LEGIBILITY_THRESHOLD = 0.6
# Deterministic-objective items the verifier passes => high band. Anything that
# falls back to a rubric judgement or a free-text read is at most middle until a
# human confirms.
_GATE_THRESHOLD = 0.85


class EvaluationEngine:
    """The three-mode evaluation engine."""

    def __init__(self, *, second_model: object | None = None, gate_threshold: float = _GATE_THRESHOLD) -> None:
        self._verify = _load_verify()
        self._gate_threshold = gate_threshold
        if second_model is not None:
            self._second_model = second_model
        elif self._verify is not None:
            self._second_model = self._verify.AbstainingSecondModel()
        else:
            self._second_model = None

    # -- public API --------------------------------------------------------
    def post_submission(self, submission: SubmissionInput) -> EvaluationOutcome:
        """Mode 1: evaluate finished, submitted work. Consequential marks are
        human-final."""
        return self._evaluate(submission, EvaluationMode.POST_SUBMISSION)

    def scanned_handwriting(self, submission: SubmissionInput) -> EvaluationOutcome:
        """Mode 2: evaluate scanned/photographed handwritten work via the OCR
        signal. Poor scan/handwriting NEVER reduces a mark — it flags review."""
        return self._evaluate(submission, EvaluationMode.SCANNED_HANDWRITING)

    def preventive_before_submission(self, submission: SubmissionInput) -> EvaluationOutcome:
        """Mode 3: check BEFORE submission so the learner can fix mistakes. This
        is helping, not grading — never consequential, never a final mark."""
        # Force non-consequential: preventive output can never be a mark of record.
        helping = SubmissionInput(
            submission_ref=submission.submission_ref,
            scored_subject=submission.scored_subject,
            responses=submission.responses,
            consequential=False,
        )
        return self._evaluate(helping, EvaluationMode.PREVENTIVE_BEFORE_SUBMISSION)

    # -- core --------------------------------------------------------------
    def _evaluate(self, submission: SubmissionInput, mode: EvaluationMode) -> EvaluationOutcome:
        per_response: list[ResponseEvaluation] = []
        review_notes: list[str] = []
        for resp in submission.responses:
            ev, note = self._evaluate_response(resp, mode)
            per_response.append(ev)
            if note:
                review_notes.append(note)

        gate = self._build_marking_gate(submission, mode, per_response)
        return EvaluationOutcome(
            mode=mode,
            submission_ref=submission.submission_ref,
            scored_subject=submission.scored_subject,
            responses=per_response,
            marking_gate=gate,
            review_notes=review_notes,
        )

    def _evaluate_response(
        self, resp: ResponseInput, mode: EvaluationMode
    ) -> tuple[ResponseEvaluation, str | None]:
        # --- Scanned-handwriting legibility gate (RULE 2) ---------------
        # Poor legibility => review, NEVER a reduced mark. We compute the score
        # exactly as for any other mode (we do not touch it), and only RAISE the
        # review flag / lower the confidence band on a legibility concern.
        legibility_review = False
        legibility_note: str | None = None
        if mode is EvaluationMode.SCANNED_HANDWRITING:
            if not resp.ocr_text_recovered:
                legibility_review = True
                legibility_note = (
                    "Scan/handwriting could not be read — flagged for human review. "
                    "No mark is reduced for legibility."
                )
            elif resp.ocr_confidence is not None and resp.ocr_confidence <= POOR_LEGIBILITY_THRESHOLD:
                legibility_review = True
                legibility_note = (
                    f"OCR legibility {resp.ocr_confidence:.2f} is low — flagged for human review. "
                    "No mark is reduced for poor handwriting or scan quality."
                )

        # --- Determine answer_state, rubric_score, base confidence -------
        if resp.expression is not None and resp.learner_answer is not None:
            answer_state, rubric_scores, band, det_note = self._objective(resp)
        elif resp.rubric is not None and resp.awards is not None:
            answer_state, rubric_scores, band, det_note = self._rubric_scored(resp)
        elif resp.free_text is not None:
            answer_state, rubric_scores, band, det_note = self._free_text(resp)
        else:
            # Nothing checkable => cannot stand alone; review.
            answer_state = AnswerState.INCOMPLETE
            rubric_scores = []
            band = EvaluationConfidenceBand.LOW
            det_note = "No checkable content (no objective handle, rubric awards, or text) — needs human review."

        # If legibility is a concern, the band can never read HIGH (we are not
        # confident the read is faithful), and review is forced. The SCORE is
        # untouched — the rule is "never reduce for handwriting," so we only move
        # confidence and the review flag.
        if legibility_review and band is EvaluationConfidenceBand.HIGH:
            band = EvaluationConfidenceBand.MIDDLE

        needs_review = legibility_review or band is not EvaluationConfidenceBand.HIGH

        rationale_parts = [p for p in (det_note, legibility_note) if p]
        rationale = " ".join(rationale_parts) or "Evaluated with high confidence."

        evaluation = ResponseEvaluation(
            question_ref=resp.question_ref,
            mode=mode,
            answer_state=answer_state,
            rubric_score=rubric_scores,
            confidence_band=band,
            needs_human_review=needs_review,
            never_penalize_handwriting=True,
            rationale=rationale,
        )
        return evaluation, legibility_note

    # -- per-kind scorers --------------------------------------------------
    def _objective(
        self, resp: ResponseInput
    ) -> tuple[AnswerState, list[RubricScore], EvaluationConfidenceBand, str]:
        """Deterministic objective item: re-compute the expression via the
        ai-fabric symbolic/numeric verifier and compare to the learner answer.

        A passing deterministic check + an agreeing second model => HIGH band
        (provisional-auto candidate). With no second model the gate stays closed,
        so even a correct deterministic check lands at MIDDLE (review) — the
        engine never stands fully alone without the cross-check.
        """
        if self._verify is None:
            return (
                AnswerState.INCOMPLETE,
                [],
                EvaluationConfidenceBand.LOW,
                "ai-fabric verify substrate not on path; cannot check objectively — needs human review.",
            )
        checks = self._verify.verify_arithmetic(str(resp.expression), float(resp.learner_answer))  # type: ignore[arg-type]
        det_passed = bool(checks) and all(c.passed for c in checks)
        agrees, sm_conf = (False, 0.0)
        if self._second_model is not None:
            agrees, sm_conf = self._second_model.cross_check(
                task_class="evaluation.response", content={"expression": resp.expression}
            )
        confidence = min(0.99 if det_passed else 0.0, sm_conf)
        gate = self._verify.ConfidenceGate(threshold=self._gate_threshold)
        gv = gate.evaluate(checks, agrees, confidence)

        if det_passed:
            answer_state = AnswerState.CORRECT
        else:
            # A wrong numeric answer reads as a procedural slip, not a wrong model,
            # unless there is more signal — the gap engine refines this later.
            answer_state = AnswerState.INCOMPLETE

        if gv.served:
            band = EvaluationConfidenceBand.HIGH
            note = "Objective answer verified deterministically and cross-checked."
        elif det_passed:
            band = EvaluationConfidenceBand.MIDDLE
            note = (
                "Objective answer verified deterministically, but the second-model cross-check "
                f"did not stand it alone ({gv.review_reason}) — provisional, needs human confirmation."
            )
        else:
            band = EvaluationConfidenceBand.MIDDLE
            note = f"Objective answer did not match the deterministic recompute ({gv.review_reason}); needs human review."
        return answer_state, [], band, note

    def _rubric_scored(
        self, resp: ResponseInput
    ) -> tuple[AnswerState, list[RubricScore], EvaluationConfidenceBand, str]:
        """Rubric-scored work. The point awards are an INPUT here (a marker's or a
        verified upstream judgement); the engine collapses them deterministically
        but, because the judgement itself is not deterministically verifiable,
        the band is at most MIDDLE (review) unless every criterion is fully
        awarded or fully zero (an unambiguous read)."""
        scored: ScoredRubric = score_response(resp.rubric, resp.awards or {}, notes=resp.award_notes)  # type: ignore[arg-type]
        normalized = scored.normalized

        if normalized >= 0.999:
            answer_state = AnswerState.CORRECT
        elif normalized <= 0.001:
            answer_state = AnswerState.MISUNDERSTOOD
        else:
            answer_state = AnswerState.INCOMPLETE

        # An unambiguous all-or-nothing rubric read can be HIGH; any partial,
        # interpretive award is MIDDLE (needs human confirmation on a mark).
        unambiguous = normalized >= 0.999 or normalized <= 0.001
        band = EvaluationConfidenceBand.HIGH if unambiguous else EvaluationConfidenceBand.MIDDLE
        note = (
            "Rubric scored from an unambiguous all-or-nothing read."
            if unambiguous
            else "Rubric scored with partial credit — interpretive, needs human confirmation."
        )
        return answer_state, scored.scores, band, note

    def _free_text(
        self, resp: ResponseInput
    ) -> tuple[AnswerState, list[RubricScore], EvaluationConfidenceBand, str]:
        """Free-text response. There is no deterministic handle, so without a live
        judging provider the engine cannot stand on a read: LOW band, review.
        It never fabricates a mark."""
        return (
            AnswerState.INCOMPLETE,
            [],
            EvaluationConfidenceBand.LOW,
            "Free-text response needs a judged read; no live evaluation provider, so it is routed to human review.",
        )

    # -- the marking gate --------------------------------------------------
    def _build_marking_gate(
        self, submission: SubmissionInput, mode: EvaluationMode, responses: list[ResponseEvaluation]
    ) -> MarkingGate:
        # Engine-recommended score: mean of per-response normalized scores.
        if responses:
            recommended = sum(r.normalized_score for r in responses) / len(responses)
        else:
            recommended = 0.0

        # The submission-level confidence band is the WEAKEST per-response band —
        # one uncertain response makes the whole mark uncertain (conservative).
        band = self._weakest_band(responses)

        # Preventive mode is NEVER a consequential mark of record.
        consequential = submission.consequential and mode is not EvaluationMode.PREVENTIVE_BEFORE_SUBMISSION

        # PERMISSION LADDER: the engine never finalises. ``final`` is False at
        # emit time; it flips only through ``confirm_mark`` on explicit human act.
        return MarkingGate(
            submission_ref=submission.submission_ref,
            consequential=consequential,
            engine_recommended_score=max(0.0, min(1.0, recommended)),
            engine_confidence_band=band,
            human_confirmed=False,
            confirmed_by=None,
            adjusted_score=None,
            final=False,
        )

    @staticmethod
    def _weakest_band(responses: list[ResponseEvaluation]) -> EvaluationConfidenceBand:
        order = {
            EvaluationConfidenceBand.LOW: 0,
            EvaluationConfidenceBand.MIDDLE: 1,
            EvaluationConfidenceBand.HIGH: 2,
        }
        if not responses:
            return EvaluationConfidenceBand.LOW
        return min((r.confidence_band for r in responses), key=lambda b: order[b])


# ---------------------------------------------------------------------------
# Human confirmation — the only path to a final consequential mark.
# ---------------------------------------------------------------------------
def confirm_mark(
    gate: MarkingGate,
    *,
    confirmed_by: UUID,
    adjusted_score: float | None = None,
) -> MarkingGate:
    """Apply an explicit HUMAN confirmation to a marking gate (PERMISSION LADDER).

    This is the ONLY way a consequential mark becomes ``final``. ``confirmed_by``
    is the opaque ref of the human marker; ``adjusted_score`` is their override
    when they change the engine recommendation. A preventive (non-consequential)
    gate can be acknowledged but never becomes a final mark of record.
    """
    final = True if gate.consequential else False
    return MarkingGate(
        submission_ref=gate.submission_ref,
        consequential=gate.consequential,
        engine_recommended_score=gate.engine_recommended_score,
        engine_confidence_band=gate.engine_confidence_band,
        human_confirmed=True,
        confirmed_by=confirmed_by,
        adjusted_score=adjusted_score,
        final=final,
    )


def is_provisional_auto(gate: MarkingGate) -> bool:
    """True when a HIGH-confidence engine recommendation may stand PROVISIONALLY
    (auto) pending human confirmation. Middle/low never qualify; a final mark is
    not provisional."""
    return (
        gate.engine_confidence_band is EvaluationConfidenceBand.HIGH
        and not gate.final
        and not gate.human_confirmed
    )
