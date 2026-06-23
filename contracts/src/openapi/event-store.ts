/**
 * Event-store capability OpenAPI spec.
 *
 * INVARIANT 5: emit a clean attributed event; the store is append-only and
 * immutable — there is deliberately NO update or delete operation here.
 * INVARIANT 6: reads come back only through a governed, consent-scoped view.
 *
 * The request/response shapes are consistent with the Zod schemas in
 * src/events: EmitEventInput on the way in, EventEnvelope on the way out.
 */

import { BEARER_SECURITY_SCHEME, ERROR_SCHEMA, type OpenApiDocument } from "./types.js";

const APP_ENUM = ["school", "learner", "platform"] as const;
const PURPOSE_ENUM = ["instruction", "assessment", "mastery", "intervention", "operations", "communication", "account"] as const;
const TYPE_ENUM = [
  "attempt.recorded",
  "assignment.created",
  "submission.created",
  "score.recorded",
  "mastery.updated",
  "intervention.fired",
  "consent.granted",
  "consent.revoked",
] as const;

export const eventStoreOpenApi: OpenApiDocument = {
  openapi: "3.1.0",
  info: {
    title: "Classess Event Store",
    version: "0.1.0",
    description:
      "Append-only, immutable, attributed event store. Emit events and read them back through governed, consent-scoped views only. No mutation, no deletion.",
  },
  servers: [{ url: "/v1/event-store", description: "Behind the gateway." }],
  security: [{ bearerAuth: [] }],
  tags: [
    { name: "emit", description: "Append a clean attributed event (INVARIANT 5)." },
    { name: "read", description: "Governed, consent-scoped reads (INVARIANT 6)." },
  ],
  paths: {
    "/events": {
      post: {
        operationId: "emitEvent",
        summary: "Append an attributed event.",
        description:
          "Validates against the event contract, stamps event_id/recorded_at/schema_version, and appends immutably. The attribution (app, canonical_uuid, purpose, consent_ref) is required and carries no PII.",
        tags: ["emit"],
        security: [{ bearerAuth: [] }],
        requestBody: { required: true, content: { "application/json": { schema: { $ref: "#/components/schemas/EmitEventInput" } } } },
        responses: {
          "201": { description: "Event appended.", content: { "application/json": { schema: { $ref: "#/components/schemas/EventEnvelope" } } } },
          "403": { description: "Consent/policy denied.", content: { "application/json": { schema: ERROR_SCHEMA } } },
          "422": { description: "Failed the event contract.", content: { "application/json": { schema: ERROR_SCHEMA } } },
        },
      },
      get: {
        operationId: "readEvents",
        summary: "Read events through a governed, consent-scoped view.",
        description:
          "Returns only events the caller is permitted to read under a satisfied consent + purpose check. The store is never queried directly; this view is the only read path.",
        tags: ["read"],
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "canonical_uuid", in: "query", required: false, description: "Opaque subject filter.", schema: { type: "string", format: "uuid" } },
          { name: "type", in: "query", required: false, schema: { type: "string", enum: [...TYPE_ENUM] } },
          { name: "purpose", in: "query", required: true, description: "Purpose asserted for this read (INVARIANT 6).", schema: { type: "string", enum: [...PURPOSE_ENUM] } },
          { name: "since", in: "query", required: false, schema: { type: "string", format: "date-time" } },
          { name: "limit", in: "query", required: false, schema: { type: "integer", minimum: 1, maximum: 500 } },
        ],
        responses: {
          "200": { description: "Scoped event page.", content: { "application/json": { schema: { type: "array", items: { $ref: "#/components/schemas/EventEnvelope" } } } } },
          "403": { description: "Consent/policy denied.", content: { "application/json": { schema: ERROR_SCHEMA } } },
        },
      },
    },
    "/events/{event_id}": {
      get: {
        operationId: "readEvent",
        summary: "Read a single event through the governed view.",
        tags: ["read"],
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "event_id", in: "path", required: true, schema: { type: "string", format: "uuid" } },
          { name: "purpose", in: "query", required: true, schema: { type: "string", enum: [...PURPOSE_ENUM] } },
        ],
        responses: {
          "200": { description: "The event.", content: { "application/json": { schema: { $ref: "#/components/schemas/EventEnvelope" } } } },
          "403": { description: "Consent/policy denied.", content: { "application/json": { schema: ERROR_SCHEMA } } },
          "404": { description: "Not found or not visible to caller.", content: { "application/json": { schema: ERROR_SCHEMA } } },
        },
      },
    },
  },
  components: {
    securitySchemes: { bearerAuth: BEARER_SECURITY_SCHEME },
    schemas: {
      EventAttribution: {
        type: "object",
        description: "Stamped on every event. Opaque identity + app + purpose + consent_ref. No PII.",
        properties: {
          app: { type: "string", enum: [...APP_ENUM] },
          canonical_uuid: { type: "string", format: "uuid", description: "Opaque identity ref (INVARIANT 1, 2)." },
          purpose: { type: "string", enum: [...PURPOSE_ENUM] },
          consent_ref: { type: "string", format: "uuid", description: "Consent record this event was captured under (INVARIANT 6)." },
        },
        required: ["app", "canonical_uuid", "purpose", "consent_ref"],
      },
      EmitEventInput: {
        type: "object",
        description: "Producer input. The store assigns event_id, recorded_at and schema_version.",
        properties: {
          app: { type: "string", enum: [...APP_ENUM] },
          canonical_uuid: { type: "string", format: "uuid" },
          purpose: { type: "string", enum: [...PURPOSE_ENUM] },
          consent_ref: { type: "string", format: "uuid" },
          occurred_at: { type: "string", format: "date-time" },
          type: { type: "string", enum: [...TYPE_ENUM] },
          payload: { type: "object", description: "Typed per `type` per the event contract (discriminated union).", additionalProperties: true },
        },
        required: ["app", "canonical_uuid", "purpose", "consent_ref", "type", "payload"],
      },
      EventEnvelope: {
        type: "object",
        description: "Stored, immutable event.",
        properties: {
          event_id: { type: "string", format: "uuid" },
          schema_version: { type: "string", enum: ["v1"] },
          occurred_at: { type: "string", format: "date-time" },
          recorded_at: { type: "string", format: "date-time" },
          app: { type: "string", enum: [...APP_ENUM] },
          canonical_uuid: { type: "string", format: "uuid" },
          purpose: { type: "string", enum: [...PURPOSE_ENUM] },
          consent_ref: { type: "string", format: "uuid" },
          type: { type: "string", enum: [...TYPE_ENUM] },
          payload: { type: "object", additionalProperties: true },
        },
        required: ["event_id", "schema_version", "occurred_at", "recorded_at", "app", "canonical_uuid", "purpose", "consent_ref", "type", "payload"],
      },
    },
  },
};
