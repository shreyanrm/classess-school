/**
 * Minimal OpenAPI 3.1 typing surface, sufficient to express the Classess
 * capability specs as typed, importable TS objects. We deliberately keep this
 * narrow rather than pulling a heavy dependency — the specs only use the subset
 * defined here, and consumers get full type-checking against it.
 */

export interface OpenApiInfo {
  title: string;
  version: string;
  description?: string;
}

export interface OpenApiServer {
  url: string;
  description?: string;
}

export interface OpenApiSchema {
  type?: "object" | "array" | "string" | "number" | "integer" | "boolean" | "null";
  format?: string;
  description?: string;
  enum?: readonly (string | number | boolean | null)[];
  properties?: Record<string, OpenApiSchema | OpenApiRef>;
  required?: readonly string[];
  items?: OpenApiSchema | OpenApiRef;
  additionalProperties?: boolean | OpenApiSchema | OpenApiRef;
  nullable?: boolean;
  minimum?: number;
  maximum?: number;
  oneOf?: (OpenApiSchema | OpenApiRef)[];
  discriminator?: { propertyName: string };
  example?: unknown;
}

export interface OpenApiRef {
  $ref: string;
}

export interface OpenApiMediaType {
  schema: OpenApiSchema | OpenApiRef;
}

export interface OpenApiRequestBody {
  description?: string;
  required?: boolean;
  content: Record<string, OpenApiMediaType>;
}

export interface OpenApiResponse {
  description: string;
  content?: Record<string, OpenApiMediaType>;
}

export interface OpenApiParameter {
  name: string;
  in: "query" | "header" | "path" | "cookie";
  required?: boolean;
  description?: string;
  schema: OpenApiSchema | OpenApiRef;
}

export interface OpenApiOperation {
  operationId: string;
  summary: string;
  description?: string;
  tags?: string[];
  security?: Record<string, string[]>[];
  parameters?: OpenApiParameter[];
  requestBody?: OpenApiRequestBody;
  responses: Record<string, OpenApiResponse>;
}

export interface OpenApiPathItem {
  get?: OpenApiOperation;
  post?: OpenApiOperation;
  put?: OpenApiOperation;
  delete?: OpenApiOperation;
  patch?: OpenApiOperation;
}

export interface OpenApiSecurityScheme {
  type: "http" | "apiKey" | "oauth2" | "openIdConnect";
  scheme?: string;
  bearerFormat?: string;
  description?: string;
  name?: string;
  in?: "query" | "header" | "cookie";
}

export interface OpenApiComponents {
  schemas?: Record<string, OpenApiSchema | OpenApiRef>;
  securitySchemes?: Record<string, OpenApiSecurityScheme>;
}

export interface OpenApiDocument {
  openapi: "3.1.0";
  info: OpenApiInfo;
  servers?: OpenApiServer[];
  security?: Record<string, string[]>[];
  tags?: { name: string; description?: string }[];
  paths: Record<string, OpenApiPathItem>;
  components?: OpenApiComponents;
}

/**
 * Every capability sits behind the gateway (INVARIANT 3) — a verified identity
 * token is required for every request. This is the shared bearer scheme all
 * specs reference.
 */
export const BEARER_SECURITY_SCHEME: OpenApiSecurityScheme = {
  type: "http",
  scheme: "bearer",
  bearerFormat: "JWT",
  description:
    "Gateway-verified identity token. INVARIANT 3: no route is reachable unauthenticated; RBAC and ABAC are enforced at the wall.",
};

/** A standard error response shape reused across specs. */
export const ERROR_SCHEMA: OpenApiSchema = {
  type: "object",
  description: "Standard error. Never contains PII or secret values (INVARIANT 1, 4).",
  properties: {
    code: { type: "string" },
    message: { type: "string" },
    request_id: { type: "string", format: "uuid" },
  },
  required: ["code", "message"],
};
