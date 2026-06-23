/**
 * Payloads for the remaining meaningful event types, plus the cross-cutting
 * verification (generate-and-verify) and permission-ladder contracts that the
 * payloads reference.
 */

import { z } from "zod";
import { CanonicalUuid, InstitutionId, OntologyRef, Purpose } from "./primitives.js";
import { GapEvidence } from "./gaps.js";
import { MasteryReading } from "./mastery.js";

/**
 * INVARIANT 7: generate-and-verify. No generated content is served unverified.
 * Anything produced by the AI fabric carries this verification stamp, and a
 * confidence gate refuses anything below threshold. The substrate is Ring 1;
 * this is its contract.
 */
export const VerificationStatus = z.enum(["pending", "passed", "failed", "human-override"]);
export type VerificationStatus = z.infer<typeof VerificationStatus>;

export const Verification = z.object({
  status: VerificationStatus,
  confidence: z.number().min(0).max(1).describe("Verifier confidence in [0,1]."),
  gate_threshold: z.number().min(0).max(1).describe("The confidence gate; content below this is refused."),
  checks: z
    .array(
      z.object({
        name: z.string(),
        passed: z.boolean(),
        detail: z.string().optional(),
      })
    )
    .describe("Deterministic checks plus second-model cross-check results."),
});
export type Verification = z.infer<typeof Verification>;

/**
 * INVARIANT 8: the permission ladder on any agent action. Anything that sends,
 * submits, publishes, deletes, or charges requires explicit human approval.
 */
export const PermissionRung = z.enum(["recommend", "prepare", "execute-with-permission", "safe-automatic"]);
export type PermissionRung = z.infer<typeof PermissionRung>;

// ---------------------------------------------------------------------------
// Coursework lifecycle
// ---------------------------------------------------------------------------

export const AssignmentCreatedPayload = z.object({
  assignment_id: z.string().uuid(),
  institution_id: InstitutionId,
  created_by: CanonicalUuid.describe("Opaque ref to the authoring teacher."),
  ontology: OntologyRef.describe("What the assignment assesses."),
  title: z.string(),
  due_at: z.string().datetime({ offset: true }).optional(),
  verification: Verification.optional().describe("Present when the assignment content was AI-generated."),
});
export type AssignmentCreatedPayload = z.infer<typeof AssignmentCreatedPayload>;

export const SubmissionCreatedPayload = z.object({
  submission_id: z.string().uuid(),
  assignment_id: z.string().uuid(),
  submitted_by: CanonicalUuid.describe("Opaque ref to the submitting learner."),
  attempt_ids: z.array(z.string().uuid()).describe("Attempt events that make up this submission."),
  submitted_at: z.string().datetime({ offset: true }),
});
export type SubmissionCreatedPayload = z.infer<typeof SubmissionCreatedPayload>;

export const ScoreMode = z.enum(["post-submission", "scanned-handwriting", "preventive-before-submission"]);
export type ScoreMode = z.infer<typeof ScoreMode>;

export const ScoreRecordedPayload = z.object({
  score_id: z.string().uuid(),
  submission_id: z.string().uuid(),
  scored_subject: CanonicalUuid.describe("Opaque ref to the learner being scored."),
  ontology: OntologyRef,
  mode: ScoreMode,
  raw_score: z.number().min(0).max(1).describe("Normalized score in [0,1]."),
  confidence_band: z.enum(["low", "medium", "high"]).describe("How confident the evaluator is; consequential marks are human-final."),
  human_final: z.boolean().describe("True once a human has confirmed a consequential mark."),
  verification: Verification.optional(),
});
export type ScoreRecordedPayload = z.infer<typeof ScoreRecordedPayload>;

// ---------------------------------------------------------------------------
// Mastery + intervention
// ---------------------------------------------------------------------------

export const MasteryUpdatedPayload = z.object({
  subject: CanonicalUuid.describe("Opaque ref to the learner whose mastery changed."),
  ontology: OntologyRef,
  reading: MasteryReading,
  gaps: z.array(GapEvidence).describe("Gaps detected for this node at this update."),
  source_event_ids: z.array(z.string().uuid()).describe("Lineage: the events this update was computed from."),
});
export type MasteryUpdatedPayload = z.infer<typeof MasteryUpdatedPayload>;

export const InterventionFiredPayload = z.object({
  intervention_id: z.string().uuid(),
  subject: CanonicalUuid.describe("Opaque ref to the learner the intervention is for."),
  owner: CanonicalUuid.describe("Opaque ref to the human who owns/approves the action."),
  gap: GapEvidence.describe("The gap this intervention responds to."),
  rung: PermissionRung.describe("Where this action sits on the permission ladder."),
  approved_by: CanonicalUuid.optional().describe("Set once a human approves an execute-with-permission action."),
  due_at: z.string().datetime({ offset: true }).optional(),
  consequence: z.string().describe("Plain-language statement of what happens if this is or is not actioned."),
});
export type InterventionFiredPayload = z.infer<typeof InterventionFiredPayload>;

// ---------------------------------------------------------------------------
// Consent lifecycle (INVARIANT 6)
// ---------------------------------------------------------------------------

export const AgeTier = z.enum(["child", "teen", "adult"]);
export type AgeTier = z.infer<typeof AgeTier>;

export const ConsentGrantedPayload = z.object({
  consent_id: z.string().uuid(),
  scope: z.string().describe("The data scope this consent covers."),
  purpose: Purpose,
  age_tier: AgeTier,
  granted_by: CanonicalUuid.describe("Opaque ref to whoever granted it (self, or guardian for a child/teen)."),
});
export type ConsentGrantedPayload = z.infer<typeof ConsentGrantedPayload>;

export const ConsentRevokedPayload = z.object({
  consent_id: z.string().uuid(),
  revoked_by: CanonicalUuid,
  reason: z.string().optional(),
});
export type ConsentRevokedPayload = z.infer<typeof ConsentRevokedPayload>;
