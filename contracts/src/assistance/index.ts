/**
 * The assistance ladder (B7 — the assistance ladder that fades as competence
 * grows).
 *
 * Ordered from most support to none:
 *   Learn → Coach → Hint → Work-with-me → Check-my-work → Independent
 *
 * The rungs themselves are defined once, in the evidence layer
 * (events/attempt.ts AssistanceLevel + ASSISTANCE_LEVEL_DOCS), because every
 * attempt is stamped with the rung actually used. This module re-exports that
 * single source of truth and adds the ordered ladder plus the HELPING-vs-
 * EVALUATING classification the workflow runtime needs.
 *
 * The distinction matters: while the system is HELPING, the work is SUPPORTED
 * and contributes evidence about what the learner can do WITH help. Only the
 * Independent rung is an unaided demonstration — the only rung that can confirm
 * independent mastery. Check-my-work is the seam: the learner produces alone,
 * the system verifies after, so it is treated as helping (a check), not an
 * unaided demonstration.
 */

import { z } from "zod";
import { AssistanceLevel, ASSISTANCE_LEVEL_DOCS } from "../events/index.js";

// Re-export the rung enum + docs so consumers can import the whole ladder from here.
export { AssistanceLevel, ASSISTANCE_LEVEL_DOCS };

/**
 * The ladder in order, most support to none. Index is the rung's position; the
 * learner climbs DOWN (toward Independent) as competence grows.
 */
export const ASSISTANCE_LADDER = [
  "Learn",
  "Coach",
  "Hint",
  "Work-with-me",
  "Check-my-work",
  "Independent",
] as const;
export type AssistanceRung = (typeof ASSISTANCE_LADDER)[number];

/** Whether a rung is the system HELPING the learner, or EVALUATING what they can do unaided. */
export const AssistanceMode = z.enum(["helping", "evaluating"]);
export type AssistanceMode = z.infer<typeof AssistanceMode>;

/**
 * Map a rung to helping vs evaluating. Only `Independent` is evaluating (an
 * unaided demonstration); every other rung — including Check-my-work — is
 * helping and produces SUPPORTED evidence.
 */
export function assistanceModeOf(rung: AssistanceRung): z.infer<typeof AssistanceMode> {
  return rung === "Independent" ? "evaluating" : "helping";
}

/** The position of a rung on the ladder (0 = most support, 5 = none). */
export function assistanceRungIndex(rung: AssistanceRung): number {
  return ASSISTANCE_LADDER.indexOf(rung);
}

/**
 * Whether evidence produced at this rung is an unaided demonstration that can
 * confirm independent mastery. True only for `Independent`.
 */
export function isUnaidedDemonstration(rung: AssistanceRung): boolean {
  return rung === "Independent";
}
