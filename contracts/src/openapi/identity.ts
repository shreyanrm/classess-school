/**
 * Identity capability OpenAPI spec.
 *
 * Auth/token issuance (phone-OTP-first), membership + scope resolution, and
 * consent checks. The identity layer is where consent is captured (INVARIANT 6)
 * and where the opaque canonical_uuid is the only identity handle that leaves
 * the vault (INVARIANT 1, 2).
 */

import { BEARER_SECURITY_SCHEME, ERROR_SCHEMA, type OpenApiDocument } from "./types.js";

export const identityOpenApi: OpenApiDocument = {
  openapi: "3.1.0",
  info: {
    title: "Classess Identity",
    version: "0.1.0",
    description:
      "Canonical identity, app membership and scope, and consent. PII is vaulted and segregated; only the opaque canonical_uuid crosses this boundary.",
  },
  servers: [{ url: "/v1/identity", description: "Behind the gateway." }],
  tags: [
    { name: "auth", description: "Token issuance and verification (phone-OTP-first; Google/Apple supported)." },
    { name: "membership", description: "App membership and scope resolution (RBAC inputs)." },
    { name: "consent", description: "Consent capture and checks (INVARIANT 6)." },
  ],
  paths: {
    "/auth/otp/start": {
      post: {
        operationId: "authOtpStart",
        summary: "Begin phone-OTP authentication.",
        tags: ["auth"],
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                type: "object",
                properties: {
                  phone: { type: "string", description: "E.164 phone. Handled inside the identity boundary; never logged." },
                  app: { type: "string", enum: ["school", "learner", "platform"] },
                },
                required: ["phone", "app"],
              },
            },
          },
        },
        responses: {
          "202": {
            description: "OTP dispatched.",
            content: {
              "application/json": {
                schema: { type: "object", properties: { challenge_id: { type: "string", format: "uuid" } }, required: ["challenge_id"] },
              },
            },
          },
          "429": { description: "Rate limited.", content: { "application/json": { schema: ERROR_SCHEMA } } },
        },
      },
    },
    "/auth/otp/verify": {
      post: {
        operationId: "authOtpVerify",
        summary: "Verify OTP and issue an identity token.",
        tags: ["auth"],
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                type: "object",
                properties: {
                  challenge_id: { type: "string", format: "uuid" },
                  code: { type: "string" },
                },
                required: ["challenge_id", "code"],
              },
            },
          },
        },
        responses: {
          "200": {
            description: "Authenticated. Returns a gateway-verifiable token and the opaque canonical_uuid.",
            content: { "application/json": { schema: { $ref: "#/components/schemas/TokenResponse" } } },
          },
          "401": { description: "Invalid or expired code.", content: { "application/json": { schema: ERROR_SCHEMA } } },
        },
      },
    },
    "/auth/token/introspect": {
      post: {
        operationId: "authTokenIntrospect",
        summary: "Verify a token and return its claims (used by the gateway).",
        tags: ["auth"],
        security: [{ bearerAuth: [] }],
        responses: {
          "200": {
            description: "Token claims.",
            content: { "application/json": { schema: { $ref: "#/components/schemas/TokenClaims" } } },
          },
          "401": { description: "Invalid token.", content: { "application/json": { schema: ERROR_SCHEMA } } },
        },
      },
    },
    "/memberships/resolve": {
      get: {
        operationId: "resolveMemberships",
        summary: "Resolve active memberships and scopes for the bearer identity.",
        description: "Returns RBAC/ABAC inputs the gateway evaluates at the wall. Time-bound memberships only.",
        tags: ["membership"],
        security: [{ bearerAuth: [] }],
        parameters: [{ name: "app", in: "query", required: false, schema: { type: "string", enum: ["school", "learner", "platform"] } }],
        responses: {
          "200": {
            description: "Active memberships.",
            content: { "application/json": { schema: { type: "array", items: { $ref: "#/components/schemas/Membership" } } } },
          },
        },
      },
    },
    "/consent/check": {
      post: {
        operationId: "consentCheck",
        summary: "Check whether a consent + purpose is satisfied for a scope.",
        description: "INVARIANT 6: every cross-context read is gated on this check.",
        tags: ["consent"],
        security: [{ bearerAuth: [] }],
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                type: "object",
                properties: {
                  canonical_uuid: { type: "string", format: "uuid" },
                  scope: { type: "string" },
                  purpose: {
                    type: "string",
                    enum: ["instruction", "assessment", "mastery", "intervention", "operations", "communication", "account"],
                  },
                },
                required: ["canonical_uuid", "scope", "purpose"],
              },
            },
          },
        },
        responses: {
          "200": {
            description: "Decision.",
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    satisfied: { type: "boolean" },
                    consent_ref: { type: "string", format: "uuid", nullable: true },
                  },
                  required: ["satisfied"],
                },
              },
            },
          },
        },
      },
    },
  },
  components: {
    securitySchemes: { bearerAuth: BEARER_SECURITY_SCHEME },
    schemas: {
      TokenResponse: {
        type: "object",
        properties: {
          access_token: { type: "string", description: "Gateway-verifiable JWT. No PII in claims." },
          token_type: { type: "string", enum: ["bearer"] },
          expires_in: { type: "integer" },
          canonical_uuid: { type: "string", format: "uuid", description: "Opaque identity ref (INVARIANT 1, 2)." },
        },
        required: ["access_token", "token_type", "expires_in", "canonical_uuid"],
      },
      TokenClaims: {
        type: "object",
        description: "Decoded token claims. Carries only the opaque canonical_uuid and authz inputs, never PII.",
        properties: {
          canonical_uuid: { type: "string", format: "uuid" },
          app: { type: "string", enum: ["school", "learner", "platform"] },
          memberships: { type: "array", items: { $ref: "#/components/schemas/Membership" } },
          expires_at: { type: "string", format: "date-time" },
        },
        required: ["canonical_uuid", "app", "expires_at"],
      },
      Membership: {
        type: "object",
        properties: {
          app: { type: "string", enum: ["school", "learner", "platform"] },
          role: { type: "string", enum: ["admin", "teacher", "student", "parent"] },
          scope: { type: "string", description: "ABAC scope, e.g. institution/grade/section identifiers." },
          granted_at: { type: "string", format: "date-time" },
          revoked_at: { type: "string", format: "date-time", nullable: true },
        },
        required: ["app", "role", "scope", "granted_at"],
      },
    },
  },
};
