/**
 * The mastery model.
 *
 *   Mastery = Performance x Reliability x Independence x Difficulty x Recency x Consistency
 *
 * Mastery is never an average and is never collapsed to a single opaque number
 * at the contract level. The six dimensions are kept explicit, each in [0,1],
 * each documented, so that:
 *   - the learner can be shown WHY a mastery reading is what it is,
 *   - the Independence dimension can separate "can do alone" from "only with
 *     help" (the support-dependency gap),
 *   - downstream surfaces render plain language, never the raw formula.
 *
 * The composite is a PRODUCT of the dimensions, not a sum: a near-zero on any
 * dimension (e.g. zero independence) must pull the whole reading down. That is
 * the design intent — being unable to work independently caps mastery no matter
 * how strong the other dimensions are.
 */

import { z } from "zod";

/** A normalized [0,1] dimension score. */
export const DimensionScore = z
  .number()
  .min(0)
  .max(1)
  .describe("Normalized mastery dimension score in [0,1].");
export type DimensionScore = z.infer<typeof DimensionScore>;

/** The ordered list of dimension keys, for iteration and validation. */
export const MASTERY_DIMENSION_KEYS = [
  "performance",
  "reliability",
  "independence",
  "difficulty",
  "recency",
  "consistency",
] as const;
export type MasteryDimensionKey = (typeof MASTERY_DIMENSION_KEYS)[number];

/** Human-readable definition of each dimension, kept beside the schema. */
export const MASTERY_DIMENSION_DOCS: Record<MasteryDimensionKey, string> = {
  performance: "How correct the learner is on the outcome — raw success rate, the starting point.",
  reliability: "How dependable that performance is across attempts, not a single lucky run.",
  independence:
    "How much of the demonstrated performance was INDEPENDENT versus SUPPORTED. Separates what the learner can do alone from what they can only do with help. The keystone dimension.",
  difficulty: "The difficulty of the items the learner has succeeded on — easy wins weigh less than hard ones.",
  recency: "How recent the evidence is — older demonstrations decay (links to the retention gap).",
  consistency: "How stable performance is over time — erratic results read lower than a steady curve.",
};

/**
 * The six mastery dimensions. Each is explicit and documented. This object is
 * the contract — surfaces and the intelligence engine read these fields, never
 * a pre-collapsed scalar.
 */
export const MasteryDimensions = z.object({
  performance: DimensionScore.describe(MASTERY_DIMENSION_DOCS.performance),
  reliability: DimensionScore.describe(MASTERY_DIMENSION_DOCS.reliability),
  independence: DimensionScore.describe(MASTERY_DIMENSION_DOCS.independence),
  difficulty: DimensionScore.describe(MASTERY_DIMENSION_DOCS.difficulty),
  recency: DimensionScore.describe(MASTERY_DIMENSION_DOCS.recency),
  consistency: DimensionScore.describe(MASTERY_DIMENSION_DOCS.consistency),
});
export type MasteryDimensions = z.infer<typeof MasteryDimensions>;

/**
 * The weighting structure. The model is multiplicative; these weights are
 * exponents that let the engine tune how sharply each dimension pulls the
 * composite without changing the contract shape:
 *
 *   composite = PROD_d ( dimension[d] ^ weight[d] )
 *
 * Defaults are uniform (1.0 each) — a plain product — with Independence and
 * Reliability flagged as the dimensions Ring 1 is expected to emphasize. The
 * computation lives in the intelligence engine (Ring 1); this is the documented
 * contract for it.
 */
export const MASTERY_WEIGHT_MODE = "multiplicative" as const;

export const MasteryWeights = z.object({
  performance: z.number().positive(),
  reliability: z.number().positive(),
  independence: z.number().positive(),
  difficulty: z.number().positive(),
  recency: z.number().positive(),
  consistency: z.number().positive(),
});
export type MasteryWeights = z.infer<typeof MasteryWeights>;

/** Default exponents — uniform; Ring 1 may override behind this contract. */
export const DEFAULT_MASTERY_WEIGHTS: MasteryWeights = {
  performance: 1.0,
  reliability: 1.0,
  independence: 1.0,
  difficulty: 1.0,
  recency: 1.0,
  consistency: 1.0,
};

/** Mastery bands shown to humans in plain language — never the raw number. */
export const MasteryBand = z.enum([
  "not-started",
  "emerging", // shows the idea, heavily supported
  "developing", // works with hints, inconsistent
  "secure", // reliable but not yet fully independent
  "independent", // does it alone, consistently — the goal
]);
export type MasteryBand = z.infer<typeof MasteryBand>;

/**
 * A computed mastery reading for a learner against an ontology node. Carries the
 * dimensions (explicit), the composite (for ranking only), the band (for
 * display), and lineage. Emitted as the `mastery.updated` event payload.
 */
export const MasteryReading = z.object({
  dimensions: MasteryDimensions,
  composite: DimensionScore.describe(
    "The collapsed product for ranking only. Never shown raw to a learner — surfaces render the band and the dimensions."
  ),
  band: MasteryBand,
  independent: z
    .boolean()
    .describe("Convenience flag: true when the learner has crossed into independent demonstration of this node."),
});
export type MasteryReading = z.infer<typeof MasteryReading>;
