/**
 * Gateway capability OpenAPI spec — the wall.
 *
 * INVARIANT 3: every service call passes the gateway. RBAC + ABAC, schema
 * validation, audit, and routing happen here, not inside services. This spec
 * documents the generic routing contract: the wall takes a verified token,
 * evaluates policy, validates the request against the target capability schema,
 * audits it (INVARIANT 9), and forwards.
 */

import { BEARER_SECURITY_SCHEME, ERROR_SCHEMA, type OpenApiDocument } from "./types.js";

export const gatewayOpenApi: OpenApiDocument = {
  openapi: "3.1.0",
  info: {
    title: "Classess Gateway",
    version: "0.1.0",
    description:
      "The single wall. Token verification, RBAC + ABAC enforcement, schema validation, immutable audit, and routing. No capability is reachable except through here.",
  },
  servers: [{ url: "/v1", description: "Public edge — the only reachable surface." }],
  security: [{ bearerAuth: [] }],
  tags: [
    { name: "routing", description: "Generic governed routing to capabilities." },
    { name: "policy", description: "Policy decision endpoint (RBAC + ABAC)." },
  ],
  paths: {
    "/route/{capability}/{operation}": {
      post: {
        operationId: "gatewayRoute",
        summary: "Governed call into a capability operation.",
        description:
          "Verifies the token, evaluates RBAC + ABAC against the resolved memberships and request attributes, validates the body against the target capability's contract, writes an audit record, then forwards. Track 1 and Track 2 routing are configured separately at the wall (INVARIANT 11).",
        tags: ["routing"],
        security: [{ bearerAuth: [] }],
        parameters: [
          { name: "capability", in: "path", required: true, schema: { type: "string", enum: ["identity", "event-store"] } },
          { name: "operation", in: "path", required: true, schema: { type: "string" } },
          { name: "X-Consent-Purpose", in: "header", required: false, description: "Purpose asserted for this call; checked for cross-context reads.", schema: { type: "string" } },
        ],
        requestBody: {
          required: false,
          description: "Opaque payload validated against the target capability's schema before forwarding.",
          content: { "application/json": { schema: { type: "object", additionalProperties: true } } },
        },
        responses: {
          "200": { description: "Forwarded response from the capability.", content: { "application/json": { schema: { type: "object", additionalProperties: true } } } },
          "401": { description: "Missing or invalid token.", content: { "application/json": { schema: ERROR_SCHEMA } } },
          "403": { description: "Policy denied (RBAC/ABAC or unsatisfied consent).", content: { "application/json": { schema: ERROR_SCHEMA } } },
          "422": { description: "Schema validation failed.", content: { "application/json": { schema: ERROR_SCHEMA } } },
        },
      },
    },
    "/policy/evaluate": {
      post: {
        operationId: "gatewayPolicyEvaluate",
        summary: "Evaluate a policy decision without forwarding (dry-run / pre-check).",
        tags: ["policy"],
        security: [{ bearerAuth: [] }],
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: {
                type: "object",
                properties: {
                  capability: { type: "string" },
                  operation: { type: "string" },
                  resource_scope: { type: "string", description: "ABAC resource attributes (e.g. institution/grade)." },
                  purpose: { type: "string" },
                },
                required: ["capability", "operation"],
              },
            },
          },
        },
        responses: {
          "200": {
            description: "Decision with reasons (for explainability).",
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    decision: { type: "string", enum: ["allow", "deny"] },
                    reasons: { type: "array", items: { type: "string" } },
                  },
                  required: ["decision", "reasons"],
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
    schemas: {},
  },
};
