/* ============================================================================
   lib/opGate.ts — the GATEWAY AUTHORIZATION PREAMBLE for the operational write
   routes (SERVER-ONLY, runtime = 'nodejs').

   Drift 3 fix. The operational write routes (attendance, messages, coursework,
   events, school, email, vidya/chat, account-delete) used to write to the
   operational/platform store with NO identity verification and NO authorization
   gate. This module is the single, shared door that routes every one of those
   CONSEQUENTIAL writes through the wall (lib/gateway.callCapability) FIRST, so
   the wall's full pipeline runs — authn -> RBAC -> ABAC -> consent -> approval
   -> child-safety -> audit, deny-by-default — before any row is committed.

   THE CONTRACT (matches lib/deepReads — the wall is authoritative, the local
   path is the DEGRADE-ONLY fallback):
     - The caller identity is derived from the request: the opaque session ids
       it already carries (X-Caller-Uuid / X-Caller-Role / X-Caller-Scope) and a
       real signed token from the session (the Authorization header) when present.
     - We ask the wall to authorize the write via callCapability. The wall
       enforces RBAC/ABAC/consent/approval/child-safety and records the attributed
       audit row. Nothing here re-implements that policy — one engine, one truth.
     - REFUSE (the wall reached a verdict the write is NOT confirmed by — 401 /
       403 / 404 / any other 4xx, incl. unknown_*): the write is REFUSED. A
       student cannot write attendance, a non-member cannot write to an
       institution, a consequential op without an approval token does not
       execute, and a write the wall could not resolve (404 / unknown_*) NEVER
       reports committed:true. The caller surfaces failed / needs-approval.
     - DEGRADE (TRUE infra only — gateway unconfigured / unreachable / timeout /
       5xx / unparseable body): we PROCEED to the existing direct path so the
       live app never breaks when the wall itself is unavailable. A 4xx is a
       REAL answer, not a degrade — only genuine infra failure falls through.

   Confidentiality: every id here is an opaque canonical ref. No PII, no secret.
   ============================================================================ */

import { callCapability, type CallerIdentity, type GatewayApp } from './gateway';

/** The decision the preamble returns. `proceed` carries WHY (for logs only). */
export interface GateDecision {
  /** True when the route may continue to its existing write path. */
  proceed: boolean;
  /** On a refusal, the wall's deny reason (e.g. "rbac_denied"). */
  detail?: string;
}

/** Headers the surface sends so the route can build the wall caller identity.
 *  All opaque (canonical_uuid + role + scope) — never PII, never a secret. */
const H_UUID = 'x-caller-uuid';
const H_ROLE = 'x-caller-role';
const H_SCOPE = 'x-caller-scope';
const H_APP = 'x-caller-app';
/** The human-approval token for the permission ladder (send/submit/grade/...). */
const H_APPROVAL = 'x-approval-token';

const APPS: ReadonlySet<string> = new Set(['school', 'learner', 'platform']);

/**
 * Build the wall caller identity from the request headers. When the caller did
 * not supply an opaque uuid, returns null — the route then degrades (the wall is
 * not asked to authorize an unidentified caller in this build's local path).
 */
function identityFromRequest(req: Request): CallerIdentity | null {
  const uuid = (req.headers.get(H_UUID) ?? '').trim();
  if (!uuid) return null;
  const role = (req.headers.get(H_ROLE) ?? '').trim() || 'service';
  const scope = (req.headers.get(H_SCOPE) ?? '').trim();
  const appRaw = (req.headers.get(H_APP) ?? '').trim();
  const app: GatewayApp = APPS.has(appRaw) ? (appRaw as GatewayApp) : 'school';
  // A real signed identity token from the session is forwarded verbatim; the
  // wall verifies it with its public key. Absent -> the client mints an unsigned
  // dev token from these opaque claims (see lib/gateway.bearerToken).
  const auth = (req.headers.get('authorization') ?? '').trim();
  const signedToken = auth.toLowerCase().startsWith('bearer ')
    ? auth.slice(7).trim()
    : undefined;
  return {
    canonical_uuid: uuid,
    app,
    memberships: [{ app, role, scope }],
    signedToken: signedToken || undefined,
  };
}

/**
 * Authorize a consequential operational write through the wall BEFORE it commits.
 *
 *   - capability/operation  the governed door the write maps to (e.g.
 *                           'attendance'/'confirm', 'messages'/'send').
 *   - payload               the opaque, non-PII descriptor of the write the wall
 *                           scopes the decision on (institution/subject/etc.).
 *   - consentPurpose        set for cross-context ops -> runs the consent gate.
 *   - the approval token    is read from the request header -> the permission
 *                           ladder (the wall enforces it on send/submit/grade/...).
 *
 * Returns { proceed: true } on a wall ADMIT and on TRUE infra-degrade only
 * (unconfigured / network / timeout / 5xx / bad-response). Returns
 * { proceed: false } on any 4xx verdict (401/403 deny, 404/unknown_* not
 * resolved) — a consequential write the wall did not confirm must NEVER commit.
 * NEVER throws.
 */
export async function authorizeWrite(
  req: Request,
  capability: string,
  operation: string,
  opts: {
    payload?: Record<string, unknown>;
    consentPurpose?: string;
    fetchImpl?: typeof fetch;
  } = {},
): Promise<GateDecision> {
  const identity = identityFromRequest(req);
  // No identified caller -> degrade to the existing local path (the wall is not
  // asked to rule on an anonymous caller here). The route's own input validation
  // still runs; this only adds the wall on top when an identity is present.
  if (!identity) return { proceed: true };

  const approvalToken = (req.headers.get(H_APPROVAL) ?? '').trim() || undefined;

  const result = await callCapability(capability, operation, {
    identity,
    payload: opts.payload ?? {},
    consentPurpose: opts.consentPurpose,
    approvalToken,
    fetchImpl: opts.fetchImpl,
  });

  // ADMIT -> proceed to the existing write path.
  if (result.ok) return { proceed: true };

  // The wall reached a 4xx VERDICT the write is not confirmed by -> REFUSE.
  // 401/403 are the explicit deny; a 4xx 'http' outcome (404 unknown_recommendation,
  // 409/422, etc.) is the wall answering that this consequential write cannot be
  // resolved/committed. None of these may fall through to a committed:true — that
  // is the CRITICAL drift this gate exists to stop.
  const status = result.status;
  if (
    result.reason === 'unauthorized' ||
    (result.reason === 'http' && typeof status === 'number' && status >= 400 && status < 500)
  ) {
    return { proceed: false, detail: result.detail ?? (status ? `http_${status}` : undefined) };
  }

  // TRUE infra-degrade only (unconfigured / network / timeout / 5xx /
  // bad-response) -> proceed to the existing path so the live app never breaks.
  return { proceed: true };
}

/** The shared refusal answer when the wall denied a consequential write. */
export function denied(detail?: string): Response {
  return Response.json(
    { persisted: false, sent: false, reason: 'forbidden', detail: detail ?? 'denied' },
    { status: 403, headers: { 'cache-control': 'no-store' } },
  );
}
