/* ============================================================================
   Runtime wiring for the web surface.

   The surface NEVER talks to the event store or PII vault directly. Every call
   goes through the gateway (RBAC + ABAC at the wall). Until that live path is
   provisioned, the surface degrades gracefully to lib/mock.ts behind this
   interface. The env var names below follow clss.<app>.<env>.<purpose>; no
   secret value is ever read into source — only the names are declared here so
   the orchestrator can provision them.
   ============================================================================ */

/**
 * Env var NAMES the live path needs. We read whether they are present to decide
 * whether to attempt a gateway call; we never embed a value. Next.js exposes
 * only NEXT_PUBLIC_* to the browser, so the public-safe gateway base URL is the
 * one read client-side; the gateway token is server-only and never shipped to
 * the client.
 */
export const ENV_VARS = {
  /** Public base URL of the gateway (RBAC+ABAC wall). Browser-safe. */
  gatewayBaseUrl: 'NEXT_PUBLIC_CLSS_WEB_PROD_GATEWAY_URL',
  /** Server-only gateway access token. Never exposed to the client. */
  gatewayToken: 'CLSS_WEB_PROD_GATEWAY_TOKEN',
} as const;

/**
 * True when the gateway base URL is configured. When false the surface renders
 * mock data behind the same component interface — a designed degraded state,
 * not an error screen.
 */
export function isGatewayConfigured(): boolean {
  return Boolean(process.env[ENV_VARS.gatewayBaseUrl]);
}
