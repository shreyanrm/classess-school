/**
 * The unified evidence record (spec `12` — the `evidence/` module).
 *
 * INVARIANT 2: every learner-facing conclusion (a mastery reading, a confirmed
 * gap) links back to typed evidence records — attempts, scores, observations,
 * external signals — each carrying the independent-vs-supported flag. This
 * module is the ONE place that shape is defined; mastery/gaps/evaluation
 * reference it rather than re-declaring evidence inline.
 *
 * The engine that WEIGHS evidence lives in the Python spine (one engine, one
 * truth — never re-implemented in TS). This is only the typed record the engine
 * reads and writes and the `evidence.recorded` event carries.
 */

import { z } from "zod";
import { CanonicalUuid, OntologyRef } from "../events/primitives.js";
import { AttemptMode } from "../events/attempt.js";

/**
 * What KIND of signal this evidence is. Different kinds weigh differently in the
 * mastery model (an independent attempt on a hard item outweighs a supported one
 * on an easy item; a teacher observation is corroborating, not primary).
 */
export const EvidenceKind = z.enum([
  "attempt", // a learner attempt (the primary evidence — carries the independence flag)
  "score", // a recorded/evaluated score on a submission
  "observation", // a human (teacher) observation, corroborating
  "retrieval", // a spaced-retrieval result (feeds recency/retention)
  "teachback", // a teach-back demonstration (strong independence signal)
  "external", // an imported/external signal (e.g. a prior credential)
]);
export type EvidenceKind = z.infer<typeof EvidenceKind>;

export const EVIDENCE_KIND_DOCS: Record<EvidenceKind, string> = {
  attempt: "A learner attempt — the primary evidence; always carries the independent-vs-supported flag.",
  score: "A recorded or evaluated score against a submission. Consequential marks are human-final.",
  observation: "A human observation (teacher/coach) — corroborating, never the sole basis for a confirmed gap.",
  retrieval: "A spaced-retrieval result; feeds the recency and retention reads.",
  teachback: "A teach-back demonstration — a strong signal that understanding is independent and durable.",
  external: "An imported external signal (prior credential, transferred record).",
};

/**
 * A single typed evidence record. The `mode` flag (independent | supported) is
 * the keystone bit INVARIANT 2 mandates be present on every record that
 * represents a demonstration; corroborating kinds (observation/external) may
 * omit it.
 */
export const EvidenceRecord = z.object({
  evidence_id: z.string().uuid().describe("Stable id for this evidence record."),
  kind: EvidenceKind,
  subject: CanonicalUuid.describe("Opaque ref to the learner this evidence is about. Never PII."),
  ontology: OntologyRef.describe("The ontology node this evidence speaks to."),

  mode: AttemptMode.optional().describe(
    "Independent or supported — REQUIRED for demonstration kinds (attempt/teachback/retrieval/score), the keystone of the Independence dimension. May be omitted for corroborating kinds (observation/external)."
  ),

  source_event_id: z
    .string()
    .uuid()
    .describe("The attributed event this evidence was derived from — full lineage back to the immutable store."),

  weight: z
    .number()
    .min(0)
    .max(1)
    .describe("Normalized contribution weight in [0,1], assigned by the spine engine. Surfaces never compute this."),

  observed_at: z.string().datetime({ offset: true }).describe("When the evidence was produced — feeds the recency read."),
})
  .superRefine((val, ctx) => {
    const demonstrationKinds: EvidenceKind[] = ["attempt", "teachback", "retrieval", "score"];
    if (demonstrationKinds.includes(val.kind) && val.mode === undefined) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["mode"],
        message: `Evidence of kind '${val.kind}' must carry the independent-vs-supported mode flag (INVARIANT 2).`,
      });
    }
  });
export type EvidenceRecord = z.infer<typeof EvidenceRecord>;

/** True when this evidence is an unaided independent demonstration — the gold standard. */
export const isIndependentDemonstration = (e: EvidenceRecord): boolean =>
  e.mode === "independent" && (e.kind === "attempt" || e.kind === "teachback");

/**
 * The payload of the `evidence.recorded` event. A conclusion (mastery/gap) links
 * to one or more of these by `evidence_id`.
 */
export const EvidenceRecordedPayload = z.object({
  record: EvidenceRecord,
});
export type EvidenceRecordedPayload = z.infer<typeof EvidenceRecordedPayload>;
