/**
 * The ten learning-gap types.
 *
 * Each gap type needs a DIFFERENT response — collapsing them into a single
 * "struggling" signal is exactly what this taxonomy exists to prevent. A gap is
 * never confirmed from a single bad score (see GapEvidence.confirmed and the
 * requirement that the learner profile updates only on fresh, sufficient
 * evidence).
 */

import { z } from "zod";

/** Documentation for each gap type, kept alongside the enum so consumers see it. */
export const GAP_TYPE_DOCS: Record<GapType, string> = {
  prerequisite:
    "A required earlier concept is missing or weak; the current topic cannot stand on it. Response: route back to the prerequisite in the graph.",
  conceptual:
    "The underlying idea is misunderstood — the mental model is wrong, not just the execution. Response: re-explain and re-anchor the concept.",
  procedural:
    "The concept is understood but the method/steps are not reliably executed. Response: guided practice on the procedure.",
  application:
    "Knows the concept and procedure in isolation but cannot transfer it to a novel or contextual problem. Response: varied-context application practice.",
  retention:
    "Was demonstrated before but has decayed over time. Response: spaced retrieval and review.",
  language:
    "The barrier is linguistic — comprehension of the question or terminology, not the academic concept. Response: hyperlocalized language support, not re-teaching the concept.",
  accuracy:
    "Method is right but execution is error-prone (slips, miscalculation). Response: precision drills and self-checking habits.",
  speed:
    "Correct and accurate but too slow for the context (timed work, fluency). Response: fluency building, not new instruction.",
  confidence:
    "Capable when supported or unobserved but falters under self-reliance or pressure. Response: scaffolded autonomy and low-stakes wins.",
  "support-dependency":
    "Performs well only with assistance and cannot yet do it independently — the gap the Independence dimension exists to surface. Response: deliberate fading of support.",
};

/**
 * The ten gap types as a closed union. Order is meaningful for display but not
 * for severity.
 */
export const GapType = z.enum([
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
]);
export type GapType = z.infer<typeof GapType>;

/** Immutable tuple of all gap types, for iteration/validation. */
export const GAP_TYPES = GapType.options;

/**
 * A classified gap with its evidence. `confirmed` stays false until enough
 * fresh evidence accumulates — a single bad score is a signal, not a gap.
 */
export const GapEvidence = z.object({
  gap_type: GapType,
  confidence: z
    .number()
    .min(0)
    .max(1)
    .describe("Confidence that this gap is real, in [0,1]. Drives whether an intervention is even proposed."),
  confirmed: z
    .boolean()
    .describe("True only once corroborated by sufficient fresh evidence; never set from a single attempt."),
  evidence_event_ids: z
    .array(z.string().uuid())
    .min(1)
    .describe("The attempt/score events that support this classification — full lineage, never an opaque claim."),
  rationale: z.string().describe("Plain-language why-this-gap, for the explainability requirement."),
});
export type GapEvidence = z.infer<typeof GapEvidence>;
