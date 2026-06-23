/**
 * Per-capability OpenAPI 3.1 specs. These are the only thing surfaces and the
 * developer team bind to (INVARIANT 3 — everything goes through the gateway).
 */

export * from "./types.js";
export { identityOpenApi } from "./identity.js";
export { gatewayOpenApi } from "./gateway.js";
export { eventStoreOpenApi } from "./event-store.js";

import type { OpenApiDocument } from "./types.js";
import { identityOpenApi } from "./identity.js";
import { gatewayOpenApi } from "./gateway.js";
import { eventStoreOpenApi } from "./event-store.js";

/** All capability specs, keyed by capability name. */
export const openApiSpecs: Record<string, OpenApiDocument> = {
  identity: identityOpenApi,
  gateway: gatewayOpenApi,
  "event-store": eventStoreOpenApi,
};
