/* ============================================================================
   lib/gateway.ts — the SERVER-ONLY client for the live gateway (THE WALL).

   This is the web surface's single door to the live Python backend's governed
   capability surface:

       POST  {CLSS_GATEWAY_URL}/capabilities/{capability}/{operation}

   Every call passes the wall's full enforcement pipeline (rate-limit -> authn ->
   RBAC -> ABAC -> consent -> approval -> child-safety -> audit, deny-by-default).
   The web NEVER bypasses the wall; it only PREPARES a governed request and READS
   the result. Writes/auth stay on the existing Supabase/local path.

   LAWS honoured here:
     - SERVER-ONLY. The base URL is read BY NAME from process.env.CLSS_GATEWAY_URL.
       It is never a NEXT_PUBLIC var and this module is imported only by server
       route handlers / server helpers (runtime = 'nodejs'). A service key/secret
       is NEVER shipped to the client.
     - The caller identity passed to the wall is an OPAQUE canonical_uuid + role +
       scope, carried in a bearer token derived from the request session. No raw
       secret is placed in the token. For local/dev the wall accepts a clearly
       marked unsigned token ("DEV-UNSIGNED.<base64url(json)>"); in production a
       real signed identity token is supplied verbatim from the session.
     - DEGRADE: if CLSS_GATEWAY_URL is unset, or the gateway is unreachable /
       times out / returns non-2xx / is unauthorized, the client returns a clean
       { ok: false } result. The caller FALLS BACK to lib/engine so the live app
       NEVER breaks. The user-visible result is identical; the difference is the
       deep Python engine powers it when the wall is reachable.
     - Observability: one short server log line per call (gateway-hit vs
       fallback). It carries the route + outcome only — never a token, never PII.
   ============================================================================ */

/** The env var NAME the gateway base URL is read from. Server-only. */
export const GATEWAY_URL_ENV = 'CLSS_GATEWAY_URL' as const;

/**
 * The wall verifies a real signed identity token with its PUBLIC key. When the
 * deployment runs without a configured public key (local/dev), the wall accepts
 * a clearly-marked UNSIGNED token whose body is base64url(JSON of the claims).
 * We mint that body from the session's opaque ids so a local wall can resolve a
 * Principal; a production session supplies a real signed token verbatim instead.
 */
const UNSIGNED_DEV_PREFIX = 'DEV-UNSIGNED.' as const;

/** Default per-call timeout. Short, so a slow/unreachable wall degrades fast. */
const DEFAULT_TIMEOUT_MS = 4000;

// ---------------------------------------------------------------------------
// Caller identity — the opaque, session-derived form the wall accepts. NEVER a
// raw secret; only the canonical_uuid + role/scope the session already holds.
// ---------------------------------------------------------------------------

export type GatewayApp = 'school' | 'learner' | 'platform';

export interface GatewayMembership {
  /** App context this role applies in. */
  app: GatewayApp;
  /** RBAC role: admin | teacher | coordinator | learner | guardian | service. */
  role: string;
  /** ABAC scope (e.g. institution/grade). Opaque. */
  scope: string;
}

export interface CallerIdentity {
  /** Opaque canonical identifier for the caller. NEVER PII. */
  canonical_uuid: string;
  /** The app surface the caller is acting in. */
  app: GatewayApp;
  /** The caller's memberships (role + scope) for RBAC/ABAC at the wall. */
  memberships: GatewayMembership[];
  /**
   * A real signed identity token from the session, when present. Passed to the
   * wall verbatim (the wall verifies it with its public key). When absent, an
   * unsigned dev token is minted from the opaque claims above so a local wall
   * can still resolve a Principal.
   */
  signedToken?: string;
}

// ---------------------------------------------------------------------------
// Result type — a clean, typed discriminated union. A failure is ALWAYS a
// recoverable { ok: false }; this client never throws to its caller.
// ---------------------------------------------------------------------------

export type GatewayFailureReason =
  | 'unconfigured' // no CLSS_GATEWAY_URL
  | 'timeout' // the wall did not respond in time
  | 'network' // unreachable / fetch threw
  | 'unauthorized' // 401/403 from the wall (denied)
  | 'http' // other non-2xx
  | 'bad-response'; // 2xx but body could not be parsed

export interface GatewaySuccess<T> {
  ok: true;
  data: T;
  /** HTTP status the wall returned (200). */
  status: number;
}

export interface GatewayFailure {
  ok: false;
  reason: GatewayFailureReason;
  /** HTTP status when there was a response; absent for unconfigured/network. */
  status?: number;
  /** The wall's deny reason value when available (e.g. "rbac_denied"). */
  detail?: string;
}

export type GatewayResult<T> = GatewaySuccess<T> | GatewayFailure;

// ---------------------------------------------------------------------------
// Config helpers
// ---------------------------------------------------------------------------

/** Read the gateway base URL by name, normalised (no trailing slash). */
function gatewayBaseUrl(): string | null {
  const raw = process.env[GATEWAY_URL_ENV];
  if (!raw || raw.trim().length === 0) return null;
  return raw.trim().replace(/\/+$/, '');
}

/** True when the gateway base URL is configured. */
export function isGatewayAvailable(): boolean {
  return gatewayBaseUrl() !== null;
}

// ---------------------------------------------------------------------------
// Token minting — opaque claims only, never a secret.
// ---------------------------------------------------------------------------

function base64url(input: string): string {
  // Server runtime (nodejs) — Buffer is available. Fall back to btoa if not.
  if (typeof Buffer !== 'undefined') {
    return Buffer.from(input, 'utf8').toString('base64url');
  }
  // eslint-disable-next-line no-undef
  return btoa(input).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/**
 * The bearer token presented to the wall. Prefer the session's real signed
 * token; otherwise mint an UNSIGNED dev token carrying ONLY the opaque claims
 * the wall's verifier reads (canonical_uuid, app, memberships). No secret.
 */
function bearerToken(identity: CallerIdentity): string {
  if (identity.signedToken && identity.signedToken.trim().length > 0) {
    return identity.signedToken.trim();
  }
  const claims = {
    canonical_uuid: identity.canonical_uuid,
    app: identity.app,
    memberships: identity.memberships,
  };
  return UNSIGNED_DEV_PREFIX + base64url(JSON.stringify(claims));
}

// ---------------------------------------------------------------------------
// Observability — one short line, no secrets, no PII (route + outcome only).
// ---------------------------------------------------------------------------

function logOutcome(route: string, outcome: string, status?: number): void {
  // Never log the token, the identity, or any payload value.
  const tail = status !== undefined ? ` status=${status}` : '';
  // eslint-disable-next-line no-console
  console.info(`[gateway] route=${route} outcome=${outcome}${tail}`);
}

// ---------------------------------------------------------------------------
// The capability call
// ---------------------------------------------------------------------------

export interface CapabilityCallOptions {
  /** Caller identity (opaque) derived from the request session. */
  identity: CallerIdentity;
  /** Governed read/write payload. Reads require { subject_uuid }. */
  payload?: Record<string, unknown>;
  /** Cross-context purpose -> sets X-Consent-Purpose, triggering the consent gate. */
  consentPurpose?: string;
  /** Human-approval token for consequential ops (the permission ladder). */
  approvalToken?: string;
  /** Per-call timeout override (ms). */
  timeoutMs?: number;
  /** Injectable fetch for tests; defaults to global fetch. */
  fetchImpl?: typeof fetch;
}

/**
 * POST a governed capability operation through the wall. Returns a typed result;
 * NEVER throws. Any failure (unconfigured / timeout / network / 401 / 403 / non-2xx)
 * is a clean { ok: false } the caller treats as "fall back to the local engine".
 */
export async function callCapability<T = unknown>(
  capability: string,
  operation: string,
  opts: CapabilityCallOptions,
): Promise<GatewayResult<T>> {
  const route = `${capability}/${operation}`;

  const base = gatewayBaseUrl();
  if (base === null) {
    logOutcome(route, 'fallback:unconfigured');
    return { ok: false, reason: 'unconfigured' };
  }

  const doFetch = opts.fetchImpl ?? fetch;
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const url = `${base}/capabilities/${encodeURIComponent(capability)}/${encodeURIComponent(operation)}`;

  const headers: Record<string, string> = {
    'content-type': 'application/json',
    authorization: `Bearer ${bearerToken(opts.identity)}`,
  };
  if (opts.consentPurpose) headers['X-Consent-Purpose'] = opts.consentPurpose;
  if (opts.approvalToken) headers['X-Approval-Token'] = opts.approvalToken;

  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = controller
    ? setTimeout(() => controller.abort(), timeoutMs)
    : null;

  let resp: Response;
  try {
    resp = await doFetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(opts.payload ?? {}),
      signal: controller?.signal,
      // Governed reads are never cached by the framework.
      cache: 'no-store',
    });
  } catch (err) {
    if (timer) clearTimeout(timer);
    const aborted = (err as { name?: string } | null)?.name === 'AbortError';
    const reason: GatewayFailureReason = aborted ? 'timeout' : 'network';
    logOutcome(route, `fallback:${reason}`);
    return { ok: false, reason };
  }
  if (timer) clearTimeout(timer);

  // Unauthorized / denied -> fall back. 401 (no/invalid token) + 403 (RBAC/ABAC
  // /consent/approval/child-safety) are the wall's deny outcomes.
  if (resp.status === 401 || resp.status === 403) {
    let detail: string | undefined;
    try {
      const body = (await resp.json()) as { reason?: string };
      detail = body?.reason;
    } catch {
      /* body not JSON — ignore */
    }
    logOutcome(route, 'fallback:unauthorized', resp.status);
    return { ok: false, reason: 'unauthorized', status: resp.status, detail };
  }

  if (!resp.ok) {
    logOutcome(route, 'fallback:http', resp.status);
    return { ok: false, reason: 'http', status: resp.status };
  }

  let data: T;
  try {
    data = (await resp.json()) as T;
  } catch {
    logOutcome(route, 'fallback:bad-response', resp.status);
    return { ok: false, reason: 'bad-response', status: resp.status };
  }

  logOutcome(route, 'gateway-hit', resp.status);
  return { ok: true, data, status: resp.status };
}

/**
 * Convenience for the governed READ operation: POSTs {capability}/read with the
 * opaque subject and an optional view. Reads are the high-value governed surface
 * the spine owns (mastery, gaps, recommendations, intelligence/insights).
 */
export function readCapability<T = unknown>(
  capability: string,
  subjectUuid: string,
  opts: {
    identity: CallerIdentity;
    view?: string;
    consentPurpose?: string;
    timeoutMs?: number;
    fetchImpl?: typeof fetch;
  },
): Promise<GatewayResult<T>> {
  const payload: Record<string, unknown> = { subject_uuid: subjectUuid };
  if (opts.view) payload.view = opts.view;
  return callCapability<T>(capability, 'read', {
    identity: opts.identity,
    payload,
    consentPurpose: opts.consentPurpose,
    timeoutMs: opts.timeoutMs,
    fetchImpl: opts.fetchImpl,
  });
}
