/**
 * The proactive Recommendation object (A5 — the observe → interpret → recommend
 * → approve → execute → outcome → learn loop) and its approval decision.
 *
 * Every recommendation carries its evidence, confidence, owner, due date,
 * consequence of ignoring, and a plain-language "why am I seeing this" — the
 * explainability requirement (B11: every alert carries evidence, confidence,
 * owner, due date, and why I am seeing it).
 *
 * PERMISSION LADDER (INVARIANT 8): a recommendation's `ladder_stage` says how
 * far it may proceed without a human. Anything consequential
 * (send/submit/publish/delete/charge/grade) NEVER auto-fires — it sits at
 * `execute_with_permission` and waits for an explicit approval decision. Only
 * `safe_automatic`, low-risk, in-policy actions may proceed unattended.
 */

import { z } from "zod";

/**
 * The permission-ladder stage of a recommendation. Underscore-cased per the
 * Slice 1 contract surface. Mirrors the event-layer PermissionRung
 * (hyphen-cased) one-to-one; this is the workflow-runtime spelling.
 */
export const LadderStage = z.enum([
  "recommend", // surface it; the human decides everything
  "prepare", // draft/stage the action but do not perform it
  "execute_with_permission", // ready to perform — but ONLY after an explicit approval decision
  "safe_automatic", // low-risk and in-policy; may proceed without a human
]);
export type LadderStage = z.infer<typeof LadderStage>;

/** Documentation per stage. */
export const LADDER_STAGE_DOCS: Record<z.infer<typeof LadderStage>, string> = {
  recommend: "Surface the finding and the suggested action; the human decides and acts.",
  prepare: "Draft or stage the action (e.g. compose the message, build the paper) without performing it.",
  execute_with_permission:
    "The action is prepared and the agent can perform it, but ONLY once a human approves. Consequential actions live here and never auto-fire.",
  safe_automatic: "Low-risk, in-policy actions the system may perform unattended, with a full audit trail.",
};

/** Confidence band on the recommendation itself. */
export const RecommendationConfidenceBand = z.enum(["low", "medium", "high"]);
export type RecommendationConfidenceBand = z.infer<typeof RecommendationConfidenceBand>;

/** Who owns / must approve the recommendation — a role plus an opaque ref. */
export const RecommendationOwner = z.object({
  role: z.string().describe("The role responsible, e.g. 'teacher', 'coordinator'. Never a real person's name."),
  ref: z.string().uuid().describe("Opaque canonical ref to the responsible person. Never PII."),
});
export type RecommendationOwner = z.infer<typeof RecommendationOwner>;

/** A linked piece of evidence supporting the recommendation — full lineage. */
export const EvidenceRef = z.object({
  event_id: z.string().uuid().describe("The attributed event this evidence comes from."),
  summary: z.string().describe("One-line, plain-language description of what this evidence shows."),
});
export type EvidenceRef = z.infer<typeof EvidenceRef>;

/**
 * The proactive recommendation. Never auto-fires for consequential actions: the
 * superRefine enforces that anything beyond `safe_automatic` must be backed by a
 * human decision before it is acted on (carried via the approval-decision type,
 * not implicitly).
 */
export const Recommendation = z.object({
  id: z.string().uuid(),
  evidence_summary: z.string().describe("Plain-language summary of the evidence behind this recommendation."),
  evidence_refs: z.array(EvidenceRef).min(1).describe("Linked evidence events — never an opaque claim."),
  confidence_band: RecommendationConfidenceBand,
  owner: RecommendationOwner,
  due_date: z.string().datetime({ offset: true }).optional().describe("When the action is needed by, when time-bound."),
  consequence_of_ignoring: z.string().describe("Plain-language statement of what happens if this is not actioned."),
  why_am_i_seeing_this: z.string().describe("The explainability line: why this surfaced to this owner now."),
  suggested_action: z.string().describe("The concrete next step being recommended."),
  ladder_stage: LadderStage,
  is_consequential: z
    .boolean()
    .describe("True when acting sends/submits/publishes/deletes/charges/grades. Consequential actions never auto-fire."),
})
  .superRefine((val, ctx) => {
    if (val.is_consequential && val.ladder_stage === "safe_automatic") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["ladder_stage"],
        message: "A consequential recommendation can never be safe_automatic; it must wait for human approval.",
      });
    }
  });
export type Recommendation = z.infer<typeof Recommendation>;

/** The human's decision on a recommendation. */
export const ApprovalDecisionKind = z.enum(["approve", "adjust", "decline"]);
export type ApprovalDecisionKind = z.infer<typeof ApprovalDecisionKind>;

/**
 * The approval decision a human records against a recommendation. An
 * `execute_with_permission` action may proceed ONLY when an `approve` (or
 * `adjust`) decision exists, recorded by a human.
 */
export const ApprovalDecision = z.object({
  recommendation_id: z.string().uuid(),
  decision: ApprovalDecisionKind,
  decided_by: z.string().uuid().describe("Opaque canonical ref to the human who decided. Agents hold no credentials and cannot self-approve."),
  decided_at: z.string().datetime({ offset: true }),
  adjustment: z.string().optional().describe("What the human changed, required when the decision is 'adjust'."),
  note: z.string().optional().describe("Optional rationale for the audit trail."),
})
  .superRefine((val, ctx) => {
    if (val.decision === "adjust" && !val.adjustment) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["adjustment"],
        message: "An 'adjust' decision requires an adjustment description.",
      });
    }
  });
export type ApprovalDecision = z.infer<typeof ApprovalDecision>;
