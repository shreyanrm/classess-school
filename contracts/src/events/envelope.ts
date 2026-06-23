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
 */
export const EventType = z.enum([
  "attempt.recorded",
  "assignment.created",
  "submission.created",
  "score.recorded",
  "mastery.updated",
  "intervention.fired",
  "consent.granted",
  "consent.revoked",
]);
export type EventType = z.infer<typeof EventType>;

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
]);
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
