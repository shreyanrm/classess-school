/**
 * The capability registry (spec `11` + `13` — the `capabilities/` module).
 *
 * Agents act ONLY through registered, governed, least-privilege capabilities —
 * never raw model calls or direct DB access. Each capability declares, in one
 * place, everything the gateway needs to govern it:
 *
 *   - inputs/outputs (by contract schema ref, resolved against `/contracts`),
 *   - the permission-ladder level it requires (INVARIANT 8),
 *   - the events it emits (INVARIANT 5),
 *   - the consent/purpose it needs (INVARIANT 6),
 *   - its track + model tier (Track 1 live providers / Track 2 reserved slot).
 *
 * This is a thin, typed INDEX over the existing contract surface — it reuses the
 * `Capability` descriptor, `CapabilityTrack`, and `ModelTier` from `../ai`, the
 * `LadderStage` from `../recommendations`, the `Purpose` and `EventType` from
 * `../events`. It does NOT re-implement any logic; the orchestrator and the
 * Python spine read it.
 */

import { z } from "zod";
import { CapabilityScope, CapabilityTrack, ModelTier } from "../ai/index.js";
import { LadderStage } from "../recommendations/index.js";
import { EventType, Purpose } from "../events/index.js";

/**
 * The named capabilities. The spec (`11`) names these examples explicitly; the
 * module list (`13`) implies the rest. APPEND-ONLY — never remove or rename.
 */
export const CapabilityId = z.enum([
  // Spec `11` named examples.
  "generate_and_verify_content",
  "evaluate_submission",
  "compose_dashboard",
  "generate_timetable",
  "propose_substitution",
  "draft_paper",
  "suggest_intervention",
  "explain_progress",
  // The eleven module APIs (`13` b1–b11), least-privilege governed entry points.
  "configure_institution", // b1
  "track_pacing", // b2
  "generate_material", // b3
  "generate_plan", // b4
  "mark_attendance", // b5
  "create_assignment", // b6
  "serve_lesson", // b7
  "get_mastery", // b8
  "schedule_ptm", // b9
  "get_coaching", // b10
  "get_feed", // b11
]);
export type CapabilityId = z.infer<typeof CapabilityId>;

/**
 * A registry entry. Extends the thin `Capability` descriptor (`../ai`) with the
 * governance facets the gateway enforces: the exact ladder level, the typed set
 * of events the capability may emit, and the purpose it operates under.
 */
export const RegisteredCapability = z.object({
  id: CapabilityId,
  description: z.string(),
  module: z.string().describe("The owning capability module, e.g. 'b8' (learner record)."),

  input_schema_ref: z.string().describe("Contract id of the validated input schema."),
  output_schema_ref: z.string().describe("Contract id of the validated structured-output schema."),

  ladder_level: LadderStage.describe(
    "The minimum permission-ladder stage this capability requires. Anything that sends/submits/publishes/deletes/charges/grades is execute_with_permission and never auto-fires."
  ),

  purpose: Purpose.describe("The single purpose code this capability operates under (INVARIANT 6 — consent is checked against it)."),
  least_privilege: CapabilityScope.describe("The minimal data scopes the capability may read; never broader than needed."),

  emits_events: z
    .array(EventType)
    .describe("The typed set of event types this capability may emit (INVARIANT 5). Empty for pure read capabilities."),

  track: CapabilityTrack,
  model_tier: ModelTier.describe("The router tier this capability defaults to; switching is a config change."),

  requires_verification: z
    .boolean()
    .describe("True for any capability that generates served content — its output must pass the confidence gate (INVARIANT 7)."),
})
  .superRefine((val, ctx) => {
    if (val.requires_verification && val.ladder_level === "safe_automatic") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["ladder_level"],
        message: "A capability that serves generated content cannot be safe_automatic; verification + a human gate are required.",
      });
    }
  });
export type RegisteredCapability = z.infer<typeof RegisteredCapability>;

/** The registry shape: the named capabilities keyed by id. */
export const CapabilityRegistry = z.record(CapabilityId, RegisteredCapability);
export type CapabilityRegistry = z.infer<typeof CapabilityRegistry>;
