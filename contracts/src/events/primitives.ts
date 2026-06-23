/**
 * Shared primitive contracts for the Classess event/evidence layer.
 *
 * These primitives are referenced across every event payload and across the
 * OpenAPI specs and DB schema descriptions. They are intentionally minimal and
 * opaque: no value defined here ever carries or derives from PII.
 */

import { z } from "zod";

/**
 * The current schema version of the event contract. Bump this only by adding a
 * NEW versioned module (events/v2/...). v1 is immutable once shipped — invariant
 * 5: the event contract is append-only from line one and is never mutated in
 * place.
 */
export const EVENT_SCHEMA_VERSION = "v1" as const;
export type EventSchemaVersion = typeof EVENT_SCHEMA_VERSION;

/** A UUID. Used for event ids, consent refs, and the opaque canonical id. */
export const Uuid = z.string().uuid();
export type Uuid = z.infer<typeof Uuid>;

/**
 * The opaque canonical identity reference.
 *
 * INVARIANT 1 + 2: this is a random/opaque UUID that maps to a person ONLY
 * inside the segregated PII vault. It is NEVER derived from PII and NEVER
 * accompanied by PII anywhere in the event store, projections, or feature
 * store. Treat this as a meaningless token outside the vault.
 */
export const CanonicalUuid = Uuid.describe(
  "Opaque random canonical identity reference. Maps to a person only inside the PII vault. Never derived from or co-located with PII."
);
export type CanonicalUuid = z.infer<typeof CanonicalUuid>;

/**
 * A reference to a recorded consent grant.
 *
 * INVARIANT 6: consent is a primitive. Every event is stamped with the consent
 * record under which it was captured, and every cross-context read is gated on
 * a satisfied consent + purpose check.
 */
export const ConsentRef = Uuid.describe(
  "Reference to the consent record under which this event was captured. Required on every attributed event."
);
export type ConsentRef = z.infer<typeof ConsentRef>;

/**
 * The ecosystem applications. `school` is the citizen built in this repo;
 * `learner` and others are reserved so the spine contract is reusable by the
 * next citizen without re-architecture.
 */
export const AppId = z.enum(["school", "learner", "platform"]);
export type AppId = z.infer<typeof AppId>;

/**
 * Purpose codes. INVARIANT 6: purpose travels with every event and is checked
 * at read time. These are coarse, auditable buckets — fine-grained scope lives
 * in the consent record itself.
 */
export const Purpose = z.enum([
  "instruction", // teaching, lesson delivery, content composition
  "assessment", // assignments, submissions, scoring, evaluation
  "mastery", // mastery + gap computation and the learner record
  "intervention", // proactive support actions
  "operations", // attendance, timetable, institution admin
  "communication", // messages, notifications, reports to humans
  "account", // identity, membership, consent lifecycle
]);
export type Purpose = z.infer<typeof Purpose>;

/** An ISO-8601 timestamp string (UTC). */
export const Timestamp = z.string().datetime({ offset: true });
export type Timestamp = z.infer<typeof Timestamp>;

/**
 * Tenant isolation handle. INVARIANT 10: logical separation per institution.
 * Carried on operational events so the gateway and projections can enforce
 * tenant scope.
 */
export const InstitutionId = Uuid.describe("Tenant (institution) identifier for logical isolation.");
export type InstitutionId = z.infer<typeof InstitutionId>;

/**
 * Ontology references. INVARIANT-adjacent: the academic ontology is a spine
 * concern (board -> ... -> topic -> outcome -> competency -> skill). Events
 * point at ontology nodes by opaque id rather than embedding curriculum, so the
 * platform stays board-agnostic.
 */
export const OntologyRef = z.object({
  topic_id: Uuid.describe("Ontology topic node."),
  outcome_id: Uuid.optional().describe("Learning outcome node, when the event is outcome-scoped."),
  competency_id: Uuid.optional().describe("Competency node, when the event rolls up to a competency."),
  skill_id: Uuid.optional().describe("Skill node, the finest grain."),
});
export type OntologyRef = z.infer<typeof OntologyRef>;
