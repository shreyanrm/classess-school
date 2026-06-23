/**
 * The AI fabric contract (A4 — model router, capability registry, generate-and-
 * verify substrate).
 *
 * Three surfaces:
 *   - the Capability descriptor (the registry: name, input/output schema refs,
 *     track, least-privilege scope),
 *   - the GenerateRequest / GenerateResult with a verification block
 *     (INVARIANT 7: nothing generated is served unverified — `served` is true
 *     ONLY when the confidence gate passes),
 *   - the model-router selection input (task class → tier).
 *
 * NO live LLM keys exist yet. This is the deterministic-shaped contract the
 * router and substrate degrade gracefully behind; the env var that will hold a
 * provider key follows the secret convention clss.<app>.<env>.<purpose> and is
 * named where used, never hard-coded.
 */

import { z } from "zod";

// ---------------------------------------------------------------------------
// Capability registry
// ---------------------------------------------------------------------------

/**
 * The two router tracks, kept configurationally separate. Track 1 is the live
 * provider path; Track 2 is the reserved slot for self-hosted / alternative
 * models, present from the start but not required to be filled.
 */
export const CapabilityTrack = z.union([z.literal(1), z.literal(2)]);
export type CapabilityTrack = z.infer<typeof CapabilityTrack>;

/**
 * A least-privilege scope grant for a capability. The capability sees ONLY the
 * purpose + data scopes it declares; nothing wider. Agents hold no credentials —
 * scopes are resolved per-invocation by the gateway.
 */
export const CapabilityScope = z.object({
  purpose: z.string().describe("The single purpose code this capability operates under."),
  data_scopes: z.array(z.string()).describe("The minimal set of data scopes the capability may read. Least privilege — never broader than needed."),
  emits_events: z.boolean().describe("Whether invoking this capability emits attributed events."),
});
export type CapabilityScope = z.infer<typeof CapabilityScope>;

/**
 * A capability descriptor in the registry. Input/output are referenced by schema
 * id (a contract id resolved elsewhere), not inlined, so the registry stays a
 * thin index over the contract surface.
 */
export const Capability = z.object({
  name: z.string().describe("Stable capability name, e.g. 'content.generate-practice-set'."),
  description: z.string(),
  input_schema_ref: z.string().describe("Contract id of the input schema this capability validates against."),
  output_schema_ref: z.string().describe("Contract id of the structured-output schema the result is validated against."),
  track: CapabilityTrack,
  least_privilege: CapabilityScope,
  requires_verification: z
    .boolean()
    .describe("True for any capability that generates served content — its output must pass the confidence gate."),
});
export type Capability = z.infer<typeof Capability>;

// ---------------------------------------------------------------------------
// Generate-and-verify
// ---------------------------------------------------------------------------

/** A single deterministic check run against generated content (symbolic/numeric where possible). */
export const DeterministicCheck = z.object({
  name: z.string().describe("e.g. 'symbolic-equivalence', 'numeric-recompute', 'schema-valid'."),
  passed: z.boolean(),
  detail: z.string().optional(),
});
export type DeterministicCheck = z.infer<typeof DeterministicCheck>;

/**
 * The verification block on a generate result. INVARIANT 7: deterministic checks
 * (symbolic/numeric for math/physics where possible) PLUS a second-model
 * cross-check, gated by a confidence threshold. `served` is the gate's verdict.
 */
export const GenerateVerification = z.object({
  deterministic_checks: z.array(DeterministicCheck).describe("All deterministic checks run; prefer symbolic/numeric for math and physics."),
  deterministic_checks_passed: z.boolean().describe("True only when every deterministic check passed."),
  second_model_agrees: z.boolean().describe("Whether an independent second model cross-checked and agreed."),
  confidence: z.number().min(0).max(1).describe("Aggregate verifier confidence in [0,1]."),
  gate_threshold: z.number().min(0).max(1).describe("The confidence gate; content below this is refused."),
  served: z
    .boolean()
    .describe("INVARIANT 7: true ONLY when the gate passed. Nothing is served to a human unless this is true."),
})
  .superRefine((val, ctx) => {
    const gatePasses = val.deterministic_checks_passed && val.second_model_agrees && val.confidence >= val.gate_threshold;
    if (val.served && !gatePasses) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["served"],
        message: "Content cannot be served: the confidence gate did not pass (deterministic checks, second-model agreement, and threshold all required).",
      });
    }
  });
export type GenerateVerification = z.infer<typeof GenerateVerification>;

/**
 * A generation request handed to the AI fabric. Names the capability, the task
 * class for routing, the structured input payload, and a target output schema
 * ref the result must validate against.
 */
export const GenerateRequest = z.object({
  request_id: z.string().uuid(),
  capability: z.string().describe("Capability name from the registry."),
  task_class: z.string().describe("The task class used for tier routing, e.g. 'math-problem-generation'."),
  input: z.unknown().describe("Structured input; validated by the capability's input_schema_ref before dispatch."),
  output_schema_ref: z.string().describe("Contract id the result must validate against (structured-output validation)."),
  purpose: z.string().describe("Purpose code under which this generation runs — least privilege."),
});
export type GenerateRequest = z.infer<typeof GenerateRequest>;

/**
 * The result of a generation. `content` is only meaningful when
 * `verification.served` is true; when the gate refuses, the substrate returns a
 * refusal with the verification block explaining why (degrades gracefully, never
 * serves unverified content).
 */
export const GenerateResult = z.object({
  request_id: z.string().uuid(),
  capability: z.string(),
  content: z.unknown().nullable().describe("The generated content. Null when refused by the gate."),
  verification: GenerateVerification,
  refused: z.boolean().describe("True when the gate refused to serve. Mutually exclusive with verification.served."),
  provider_available: z
    .boolean()
    .describe("False when no live provider/key is configured; the deterministic path still returns a well-formed refusal."),
})
  .superRefine((val, ctx) => {
    if (val.refused === val.verification.served) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["refused"],
        message: "refused must be the inverse of verification.served.",
      });
    }
    if (val.verification.served && val.content === null) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["content"],
        message: "Served content cannot be null.",
      });
    }
  });
export type GenerateResult = z.infer<typeof GenerateResult>;

// ---------------------------------------------------------------------------
// Model router
// ---------------------------------------------------------------------------

/**
 * Router tiers. Frontier for hard/rare reasoning, mid for volume, edge for the
 * high-frequency ocean of small tasks.
 */
export const ModelTier = z.enum(["frontier", "mid", "edge"]);
export type ModelTier = z.infer<typeof ModelTier>;

export const MODEL_TIER_DOCS: Record<z.infer<typeof ModelTier>, string> = {
  frontier: "Hardest, rarest reasoning — highest capability, used sparingly.",
  mid: "High-volume capable work — the workhorse tier.",
  edge: "The high-frequency ocean of small, fast, low-stakes tasks — smallest models at the edge.",
};

/**
 * The model-router selection input: a task class plus signals the router uses to
 * pick a tier. The router maps task_class → tier; this contract is the input it
 * selects on. The env var holding the active provider key (Track 1) is named at
 * the call site following clss.<app>.<env>.<purpose>; absence degrades to a
 * deterministic refusal rather than a hard failure.
 */
export const RouterSelectionInput = z.object({
  task_class: z.string().describe("The task class to route, e.g. 'evaluation.scan-read', 'content.generate-hint'."),
  difficulty: z.number().min(0).max(1).optional().describe("Normalized expected difficulty in [0,1]; pushes toward frontier."),
  latency_sensitive: z.boolean().optional().describe("True for interactive paths that favour the edge tier."),
  requires_verification: z.boolean().describe("Whether the output must pass the generate-and-verify gate."),
});
export type RouterSelectionInput = z.infer<typeof RouterSelectionInput>;

/** The router's decision: the chosen tier plus a plain-language rationale. */
export const RouterSelection = z.object({
  task_class: z.string(),
  tier: ModelTier,
  rationale: z.string().describe("Why this tier was chosen — for observability and audit."),
});
export type RouterSelection = z.infer<typeof RouterSelection>;
