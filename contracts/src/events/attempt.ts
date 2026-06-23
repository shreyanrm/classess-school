/**
 * The attempt event — the heart of the evidence layer.
 *
 * Every time a learner attempts something, we capture not just whether it was
 * right, but HOW it was produced: independently, or with assistance, and at what
 * level of assistance. This is the raw material the Independence dimension and
 * the support-dependency gap are built from. Without the independent-vs-supported
 * flag, mastery degenerates into an average and the platform's core claim
 * collapses.
 */

import { z } from "zod";
import { OntologyRef } from "./primitives.js";

/**
 * The independent-vs-supported flag. The single most important bit in the
 * evidence layer: did the learner do this ALONE, or with help.
 */
export const AttemptMode = z.enum(["independent", "supported"]);
export type AttemptMode = z.infer<typeof AttemptMode>;

/**
 * The assistance ladder. Ordered from most support to none — this is the scaffold
 * the learner climbs down as they gain independence. `Independent` is the only
 * level that pairs with AttemptMode `independent`; every other level is
 * `supported`.
 */
export const AssistanceLevel = z.enum([
  "Learn", // full instruction / worked exposure
  "Coach", // guided, step-by-step alongside
  "Hint", // nudges only
  "Work-with-me", // collaborative, shared production
  "Check-my-work", // learner produces, system verifies after
  "Independent", // no assistance
]);
export type AssistanceLevel = z.infer<typeof AssistanceLevel>;

/** Documentation per assistance level, kept beside the enum. */
export const ASSISTANCE_LEVEL_DOCS: Record<AssistanceLevel, string> = {
  Learn: "Full instruction or a worked example — the learner is being shown.",
  Coach: "Guided step-by-step support alongside the learner as they work.",
  Hint: "Nudges and prompts only; the learner does the work.",
  "Work-with-me": "Collaborative production — learner and system build the answer together.",
  "Check-my-work": "Learner produces independently, then the system verifies after the fact.",
  Independent: "No assistance of any kind — the demonstration that mastery is built on.",
};

/**
 * Difficulty of the attempted item, normalized. Feeds the Difficulty dimension.
 */
export const Difficulty = z
  .number()
  .min(0)
  .max(1)
  .describe("Normalized item difficulty in [0,1] (0 = trivial, 1 = hardest in the ontology band).");
export type Difficulty = z.infer<typeof Difficulty>;

/**
 * The attempt event payload. Keyed to an ontology node, carrying correctness,
 * the mode/assistance pair, timing, and difficulty.
 */
export const AttemptPayload = z.object({
  attempt_id: z.string().uuid().describe("Stable id for this attempt."),
  question_id: z.string().uuid().optional().describe("Ontology question node, when the attempt targets a specific item."),
  ontology: OntologyRef.describe("What this attempt is evidence about — topic/outcome/competency/skill."),

  mode: AttemptMode.describe("Independent or supported — the keystone flag for the Independence dimension."),
  assistance_level: AssistanceLevel.describe("The level of scaffold actually used during the attempt."),

  correct: z.boolean().describe("Whether the attempt was correct."),
  score: z
    .number()
    .min(0)
    .max(1)
    .optional()
    .describe("Partial-credit score in [0,1] for non-binary items; omit for purely correct/incorrect."),

  time_taken_ms: z
    .number()
    .int()
    .nonnegative()
    .describe("Wall-clock time on the attempt in milliseconds. Feeds the speed gap and fluency reads."),
  difficulty: Difficulty,

  attempt_number: z
    .number()
    .int()
    .positive()
    .default(1)
    .describe("Which try this is on the same item — repeated attempts feed reliability and consistency."),
})
  // Enforce the mode/assistance coherence at the contract boundary so no
  // malformed evidence ever enters the immutable store.
  .superRefine((val, ctx) => {
    const isIndependentLevel = val.assistance_level === "Independent";
    if (val.mode === "independent" && !isIndependentLevel) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["mode"],
        message: "mode 'independent' requires assistance_level 'Independent'.",
      });
    }
    if (val.mode === "supported" && isIndependentLevel) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["mode"],
        message: "mode 'supported' cannot use assistance_level 'Independent'.",
      });
    }
  });
export type AttemptPayload = z.infer<typeof AttemptPayload>;
