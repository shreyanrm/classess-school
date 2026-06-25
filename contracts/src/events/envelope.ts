/**
 * The attributed event envelope and the discriminated union of all v1 event
 * payloads.
 *
 * INVARIANT 5: every meaningful action emits a clean, attributed event. Events
 * are immutable and append-only; nothing here permits mutation.
 * Attribution = app . canonical_uuid . type . purpose . consent_ref.
 */

import { z } from "zod";
import {
  AppId,
  CanonicalUuid,
  ConsentRef,
  EVENT_SCHEMA_VERSION,
  Purpose,
  Timestamp,
  Uuid,
} from "./primitives.js";
import { AttemptPayload } from "./attempt.js";
import {
  AssignmentCreatedPayload,
  ConsentGrantedPayload,
  ConsentRevokedPayload,
  InterventionFiredPayload,
  MasteryUpdatedPayload,
  ScoreRecordedPayload,
  SubmissionCreatedPayload,
} from "./payloads.js";

/**
 * The closed set of v1 event types. The string value is the wire `type` and the
 * discriminator on the payload union.
 *
 * The catalog covers the families named in `12-data-model-and-contracts.md`
 * (identity/consent, learning, mastery/evidence, coursework, content,
 * attendance/ops, workflow/agent, comms, system). It is APPEND-ONLY and grows
 * additively — never reorder or remove. The eight original families carry fully
 * typed payloads in `EventBody`; the remaining families carry the open
 * `GenericEventPayload` (a typed, attributed envelope with a structured but
 * unconstrained payload) so producers can emit them from line one without a
 * breaking schema bump. A family graduates to a strict payload by adding it to
 * the strict arm of `EventBody` in a later additive change.
 */
export const EventType = z.enum([
  // Original eight — strict payloads (see EventBody strict arm).
  "attempt.recorded",
  "assignment.created",
  "submission.created",
  "score.recorded",
  "mastery.updated",
  "intervention.fired",
  "consent.granted",
  "consent.revoked",
  // Identity/consent.
  "person.created",
  "membership.granted",
  // Learning.
  "attempt", // spec spelling alias for the learning lesson-player attempt
  "lesson.viewed",
  "prediction.committed",
  "misconception.detected",
  "misconception.resolved",
  "teachback.completed",
  "retrieval.completed",
  // Mastery/evidence.
  "evidence.recorded",
  "gap.detected",
  "gap.resolved",
  // Coursework/assessment.
  "assessment.submitted",
  "score", // spec spelling alias for a recorded score
  "evaluation.completed",
  "moderation.approved",
  "paper.generated",
  // Content.
  "content.generated",
  "content.verified",
  "content.rejected",
  // Attendance/ops.
  "attendance.marked",
  "attendance.risk",
  "attendance.reconcile_flag",
  "leave.requested",
  "substitution.proposed",
  "timetable.generated",
  "calendar.updated",
  "pacing.behind",
  // Teaching (b4).
  "plan.generated",
  "plan.submitted",
  "class.launched",
  "engagement.signal",
  "poll.run",
  "session.summarised",
  // Workflow/agent.
  "recommendation.created",
  "recommendation.actioned",
  "intervention.created",
  "intervention.outcome",
  "capability.invoked",
  "approval.given",
  // Comms/relationship.
  "message.sent",
  "notification.sent",
  "ptm.scheduled",
  "ptm.completed",
  "action.assigned",
  "proof.generated",
  // Teacher growth.
  "coaching.signal",
  "handover.created",
  // Institution/policy.
  "institution.configured",
  "policy.changed",
  "credential.issued",
  "resource.ingested",
  // System.
  "surface.viewed",
  "audit.entry",
  "break_glass.used",
]);
export type EventType = z.infer<typeof EventType>;

/**
 * The set of event types that carry a fully typed strict payload in `EventBody`.
 * Everything else in `EventType` is emitted with `GenericEventPayload`.
 */
export const STRICT_EVENT_TYPES = [
  "attempt.recorded",
  "assignment.created",
  "submission.created",
  "score.recorded",
  "mastery.updated",
  "intervention.fired",
  "consent.granted",
  "consent.revoked",
] as const satisfies readonly EventType[];

/**
 * The open payload for the catalog families that do not (yet) have a strict
 * schema. It is still attributed and consent-stamped via the envelope — only the
 * inner shape is open. This honours INVARIANT 5 ("every meaningful action emits
 * a clean, attributed, consent-stamped event") from line one without forcing a
 * strict schema for all 50+ families up front.
 */
export const GenericEventPayload = z
  .record(z.string(), z.unknown())
  .describe(
    "Structured, attributed payload for a catalog family without a strict schema yet. The envelope still carries full attribution + consent. A family graduates to a strict payload additively."
  );
export type GenericEventPayload = z.infer<typeof GenericEventPayload>;

/**
 * The discriminated union of all event payloads, keyed by `type`. Each member is
 * the envelope fields plus a typed `payload`. This is what `emitEvent` accepts
 * and what `readEvent` returns.
 */
export const EventBody = z.discriminatedUnion("type", [
  z.object({ type: z.literal("attempt.recorded"), payload: AttemptPayload }),
  z.object({ type: z.literal("assignment.created"), payload: AssignmentCreatedPayload }),
  z.object({ type: z.literal("submission.created"), payload: SubmissionCreatedPayload }),
  z.object({ type: z.literal("score.recorded"), payload: ScoreRecordedPayload }),
  z.object({ type: z.literal("mastery.updated"), payload: MasteryUpdatedPayload }),
  z.object({ type: z.literal("intervention.fired"), payload: InterventionFiredPayload }),
  z.object({ type: z.literal("consent.granted"), payload: ConsentGrantedPayload }),
  z.object({ type: z.literal("consent.revoked"), payload: ConsentRevokedPayload }),
  // The remaining catalog families carry the open GenericEventPayload — still
  // attributed + consent-stamped via the envelope. Additive: a family graduates
  // to a strict member above without breaking existing consumers.
  ...EventType.options
    .filter((t) => !(STRICT_EVENT_TYPES as readonly string[]).includes(t))
    .map((t) => z.object({ type: z.literal(t), payload: GenericEventPayload })),
] as unknown as [z.ZodObject<{ type: z.ZodLiteral<EventType>; payload: z.ZodTypeAny }>, ...z.ZodObject<{ type: z.ZodLiteral<EventType>; payload: z.ZodTypeAny }>[]]);
export type EventBody = z.infer<typeof EventBody>;

/**
 * Attribution fields stamped on every event. Carries the opaque identity, the
 * app, the purpose, and the consent ref under which the event was captured.
 * NEVER carries PII.
 */
export const EventAttribution = z.object({
  app: AppId,
  canonical_uuid: CanonicalUuid,
  purpose: Purpose,
  consent_ref: ConsentRef,
});
export type EventAttribution = z.infer<typeof EventAttribution>;

/**
 * The full stored event envelope: server-assigned ids and timestamps, the
 * attribution, the schema version, and the typed body.
 *
 * `occurred_at` is when the action happened (client truth); `recorded_at` is
 * when the store accepted it (server truth). Both are immutable once written.
 */
export const EventEnvelope = z
  .object({
    event_id: Uuid.describe("Server-assigned unique id for this event row."),
    schema_version: z.literal(EVENT_SCHEMA_VERSION),
    occurred_at: Timestamp.describe("When the action occurred (source-of-truth time)."),
    recorded_at: Timestamp.describe("When the immutable store accepted the event."),
  })
  .merge(EventAttribution)
  .and(EventBody);
export type EventEnvelope = z.infer<typeof EventEnvelope>;

/**
 * The input a producer hands to `emitEvent`. The store assigns `event_id` and
 * `recorded_at` and fixes `schema_version`; the producer supplies attribution,
 * `occurred_at`, and the typed body.
 */
export const EmitEventInput = z
  .object({
    occurred_at: Timestamp.optional().describe("Defaults to now at the store if omitted."),
  })
  .merge(EventAttribution)
  .and(EventBody);
export type EmitEventInput = z.infer<typeof EmitEventInput>;

/** Convenience: extract the payload type for a given event `type`. */
export type PayloadFor<T extends EventType> = Extract<EventBody, { type: T }>["payload"];
