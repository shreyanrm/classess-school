/**
 * The evaluation contract (B6 — the evaluation engine, CORE: correctness is
 * existential).
 *
 * Three modes, a per-response result, a rubric, and the human-final marking
 * gate. Two non-negotiables are encoded structurally:
 *   - consequential marks are HUMAN-FINAL (PERMISSION LADDER: grading needs
 *     explicit human approval; the engine recommends, a human confirms),
 *   - handwriting and scan quality NEVER reduce a mark — poor legibility flags
 *     "needs human review", it does not penalise.
 *
 * A learner judgment is never confirmed from a single bad score — that rule
 * lives in the evidence engine; this contract carries the per-response signal it
 * consumes, banded by confidence and flagged for review where uncertain.
 */

import { z } from "zod";

/**
 * The three evaluation modes. Values align with the event-layer ScoreMode so a
 * result maps cleanly onto a `score.recorded` event.
 */
export const EvaluationMode = z.enum([
  "post_submission", // the learner has submitted; evaluate the finished work
  "scanned_handwriting", // evaluate scanned/photographed handwritten work
  "preventive_before_submission", // check before submission so the learner can fix it (helping, not grading)
]);
export type EvaluationMode = z.infer<typeof EvaluationMode>;

/** Documentation per mode, kept beside the enum. */
export const EVALUATION_MODE_DOCS: Record<z.infer<typeof EvaluationMode>, string> = {
  post_submission: "The learner has submitted finished work; the engine evaluates it. Consequential marks here are human-final.",
  scanned_handwriting:
    "Evaluates scanned or photographed handwritten work. Scan/handwriting quality NEVER lowers a mark; illegible content flags needs_human_review.",
  preventive_before_submission:
    "Runs before the learner submits, so they can correct mistakes themselves. This is HELPING, not grading — it never produces a consequential mark.",
};

/**
 * How a single response landed against the expected answer. Distinct from a raw
 * score because the RESPONSE TYPE drives a different gap response:
 *   - incomplete   → procedural/speed, the learner stopped short,
 *   - misunderstood → conceptual, the mental model is wrong.
 */
export const AnswerState = z.enum(["correct", "incomplete", "misunderstood"]);
export type AnswerState = z.infer<typeof AnswerState>;

/**
 * Confidence band on the evaluation of a single response. Low/middle band, or
 * any consequential mark, must route to human review before it is final.
 */
export const EvaluationConfidenceBand = z.enum(["high", "middle", "low"]);
export type EvaluationConfidenceBand = z.infer<typeof EvaluationConfidenceBand>;

/** A single rubric criterion the response is scored against. */
export const RubricCriterion = z.object({
  criterion_id: z.string().uuid(),
  description: z.string().describe("What this criterion assesses, in plain language."),
  max_points: z.number().nonnegative().describe("Maximum points this criterion can award."),
  weight: z.number().min(0).max(1).default(1).describe("Relative weight of this criterion within the rubric, in [0,1]."),
});
export type RubricCriterion = z.infer<typeof RubricCriterion>;

/** A score awarded against one rubric criterion. */
export const RubricScore = z.object({
  criterion_id: z.string().uuid(),
  points_awarded: z.number().nonnegative(),
  max_points: z.number().nonnegative(),
  note: z.string().optional().describe("Brief, plain-language justification for this criterion's score."),
});
export type RubricScore = z.infer<typeof RubricScore>;

/**
 * The per-response evaluation result. Question reference, how the answer landed,
 * the rubric breakdown, the confidence band, and the review flag. Carries the
 * never-penalize-handwriting note so it travels with the result, not just in
 * docs.
 */
export const ResponseEvaluation = z.object({
  question_ref: z.string().uuid().describe("Ontology question node this response answers."),
  mode: EvaluationMode,
  answer_state: AnswerState,
  rubric_score: z.array(RubricScore).describe("Per-criterion breakdown. Empty for a purely correct/incorrect item."),
  confidence_band: EvaluationConfidenceBand,
  needs_human_review: z
    .boolean()
    .describe("True when the engine is not confident enough to stand alone — low/middle band, ambiguous, or illegible."),
  never_penalize_handwriting: z
    .literal(true)
    .describe(
      "Structural reminder carried on every result: handwriting and scan quality must never reduce the mark. Illegible work sets needs_human_review, it does not penalise."
    ),
  rationale: z.string().describe("Plain-language why-this-result, for explainability and human review."),
})
  // Encode the two structural rules at the contract boundary.
  .superRefine((val, ctx) => {
    if (val.confidence_band !== "high" && !val.needs_human_review) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["needs_human_review"],
        message: "A non-high confidence band must set needs_human_review true.",
      });
    }
  });
export type ResponseEvaluation = z.infer<typeof ResponseEvaluation>;

/**
 * The human-final marking gate (PERMISSION LADDER). A consequential mark is not
 * final until a human confirms it. The engine produces the recommended state;
 * `human_confirmed` flips only on explicit human action, and `final` is derived:
 * a consequential mark is final ONLY when a human has confirmed it.
 */
export const MarkingGate = z.object({
  submission_ref: z.string().uuid(),
  consequential: z
    .boolean()
    .describe("True when this mark affects a grade/record/report — these are always human-final."),
  engine_recommended_score: z.number().min(0).max(1).describe("The engine's recommended normalized score in [0,1]."),
  engine_confidence_band: EvaluationConfidenceBand,
  human_confirmed: z.boolean().describe("True only once a human marker has explicitly confirmed or adjusted the mark."),
  confirmed_by: z.string().uuid().optional().describe("Opaque canonical ref to the human who confirmed. Set with human_confirmed."),
  adjusted_score: z.number().min(0).max(1).optional().describe("The human's adjusted score, when they changed the recommendation."),
  final: z.boolean().describe("Derived: a consequential mark is final only when human_confirmed is true; preventive checks are never final marks."),
})
  .superRefine((val, ctx) => {
    if (val.consequential && val.final && !val.human_confirmed) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["final"],
        message: "A consequential mark cannot be final without human_confirmed.",
      });
    }
    if (val.human_confirmed && !val.confirmed_by) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["confirmed_by"],
        message: "human_confirmed requires confirmed_by.",
      });
    }
  });
export type MarkingGate = z.infer<typeof MarkingGate>;
