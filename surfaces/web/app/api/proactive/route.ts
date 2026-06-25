/* ============================================================================
   app/api/proactive/route.ts — the CLIENT->SERVER->GATEWAY hop for the proactive
   loop (recommend -> approve -> execute), spec 13 b11 + the permission ladder 11.

   SERVER-ONLY (runtime = 'nodejs'). The home suggestion chips, the /proactive
   page, and Vidya's recommendations are client surfaces; the governed deep-read
   seam (lib/deepReads) and the wall (lib/gateway) are server-only. This thin
   route is the bridge:

     GET  ?subject=<ref>                 -> recommend: the proactive feed, the
                                            SPINE's recommendations when the wall
                                            admits, the local list on degrade.
                                            { recommendations, permissionDenied,
                                              source }

     POST { id, decision, consequential } -> approve + execute: drives the same
                                            ENGINE recommendation (the stable id
                                            recommend minted) through the loop's
                                            real rungs:
                                              decline  -> nothing commits.
                                              approve  -> the wall's APPROVE rung
                                                          records approval.given,
                                                          we mint an approval
                                                          token, then call the
                                                          EXECUTE rung WITH the
                                                          X-Approval-Token.
                                              execute  -> (reversible) the EXECUTE
                                                          rung directly.
                                            We return the REAL execute outcome
                                            (cleared/performed/stage/reason) —
                                            NEVER an echoed decision string.
                                            { committed, outcome, performed,
                                              cleared, stage, reason, source }

   The web only PREPARES + READS the feed; the human decision is the one write,
   and a consequential one never commits without the wall's approval + the
   approval token on the EXECUTE rung. Identity is the opaque caller (uuid + role)
   from the request headers — no PII, no secret, ever returned. A wall DENY (or a
   4xx the loop could not resolve, e.g. an unknown id) surfaces as
   `permissionDenied` / `committed:false` so the surface renders the designed
   failed/needs-approval state, NEVER a silent committed:true.
   ============================================================================ */

import { readRecommendations, callerIdentity } from '@/lib/deepReads';
import { denied } from '@/lib/opGate';
import { callCapability, type CallerIdentity, type GatewayResult } from '@/lib/gateway';
import { CLASS_REF } from '@/lib/loopData';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const NO_STORE = { 'cache-control': 'no-store' } as const;

function ok(body: Record<string, unknown>, status = 200): Response {
  return Response.json(body, { status, headers: NO_STORE });
}

/** A wall deny on RBAC/ABAC/consent surfaces as a permission state, not a degrade. */
function isDenied(reason?: string): boolean {
  return reason === 'unauthorized';
}

// ---------------------------------------------------------------------------
// GET — recommend. The proactive feed, gateway-first with the local fallback.
// ---------------------------------------------------------------------------

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const subject = (url.searchParams.get('subject') ?? CLASS_REF).trim() || CLASS_REF;

  // The opaque caller identity for the wall — uuid + role from the headers the
  // surface already stamps (lib/events / lib/opData). Never PII; falls back to
  // the class scope ref so the read still resolves on the local path.
  const callerUuid = req.headers.get('x-caller-uuid') || subject;
  const role = req.headers.get('x-caller-role') || 'teacher';
  const identity = callerIdentity({ canonicalUuid: callerUuid, role, scope: subject });

  const read = await readRecommendations(subject, identity);

  // A wall ACTIVE deny (not merely unreachable) -> the permission-denied state.
  const permissionDenied = isDenied(read.fallbackReason);

  return ok({
    recommendations: read.data,
    permissionDenied,
    source: read.source,
  });
}

// ---------------------------------------------------------------------------
// POST — approve + execute. The one write of the loop, driven through the SAME
// engine recommendation the GET minted (the stable id). For a consequential
// action the human APPROVE rung records approval.given; we then mint an approval
// token and call the EXECUTE rung WITH the X-Approval-Token (the permission
// ladder). We return the REAL execute outcome, never an echoed decision string.
// ---------------------------------------------------------------------------

const CAP = 'intelligence-views';
const CONSENT = 'intelligence.recommendations';

/** The opaque caller identity for the wall, from the headers the surface stamps. */
function identityFromRequest(req: Request, subject: string): CallerIdentity {
  const callerUuid = req.headers.get('x-caller-uuid') || subject;
  const role = req.headers.get('x-caller-role') || 'teacher';
  const scope = req.headers.get('x-caller-scope') || subject;
  const auth = (req.headers.get('authorization') ?? '').trim();
  const signedToken = auth.toLowerCase().startsWith('bearer ') ? auth.slice(7).trim() : undefined;
  return callerIdentity({ canonicalUuid: callerUuid, role, scope, signedToken });
}

/** A 4xx is a REAL verdict (deny / unknown_* / unresolved) -> the consequential
 *  write is REFUSED, never committed. Only true infra (network/timeout/5xx/
 *  unconfigured/bad-response) is a degrade. Mirrors lib/opGate.authorizeWrite. */
function isHardFailure(r: GatewayResult<unknown>): boolean {
  if (r.ok) return false;
  if (r.reason === 'unauthorized') return true;
  return r.reason === 'http' && typeof r.status === 'number' && r.status >= 400 && r.status < 500;
}

/** The engine outcome the EXECUTE rung returns (workflow_app.do_execute). */
interface ExecuteOutcome {
  cleared?: boolean;
  performed?: boolean;
  stage?: string;
  reason?: string;
}

export async function POST(req: Request): Promise<Response> {
  let body: { id?: string; decision?: string; consequential?: boolean; subject?: string };
  try {
    body = (await req.json()) as typeof body;
  } catch {
    return ok({ committed: false, reason: 'bad-request' }, 400);
  }

  const id = String(body.id ?? '').trim();
  const decision = String(body.decision ?? '').trim();
  if (!id || (decision !== 'approve' && decision !== 'execute' && decision !== 'decline')) {
    return ok({ committed: false, reason: 'invalid-input' }, 400);
  }

  // Decline never commits anything — it only sets the item aside.
  if (decision === 'decline') {
    return ok({ committed: false, outcome: 'declined', source: 'fallback' });
  }

  const subject = String(body.subject ?? '').trim() || CLASS_REF;
  const identity = identityFromRequest(req, subject);
  const consequential = Boolean(body.consequential);
  const payload = { recommendation_id: id, subject_uuid: subject, decision };

  // A consequential action: APPROVE first (records approval.given), then mint the
  // approval token and run EXECUTE with it. The approval token is minted ONLY
  // after the wall admits + the engine clears the human decision — never before.
  let approvalToken: string | undefined;
  if (decision === 'approve' || consequential) {
    const approved = await callCapability<{ cleared?: boolean }>(CAP, 'approve', {
      identity,
      payload,
      consentPurpose: CONSENT,
    });
    // A 4xx on approve (deny / unknown id) is a REAL FAILURE -> needs-approval.
    if (isHardFailure(approved)) return denied(approved.ok ? undefined : approved.detail);
    // A true infra-degrade on approve -> we cannot honestly claim a consequential
    // op committed (no recorded approval). Surface needs-approval, not committed.
    if (!approved.ok && consequential) {
      return ok({ committed: false, outcome: 'needs-approval', source: 'fallback' });
    }
    // Approval recorded -> mint the token the EXECUTE rung's wall gate requires.
    approvalToken = `APPROVAL.${id}.${Date.now()}`;
  }

  // EXECUTE — the real action. The wall forces the X-Approval-Token (the EXECUTE
  // capability is consequential); we pass the token minted above. The engine
  // returns the REAL outcome (cleared/performed/stage/reason).
  const executed = await callCapability<ExecuteOutcome>(CAP, 'execute', {
    identity,
    payload,
    approvalToken: approvalToken ?? `APPROVAL.${id}.${Date.now()}`,
  });

  // A 4xx on execute (deny / no token / unknown id) is a REAL FAILURE.
  if (isHardFailure(executed)) return denied(executed.ok ? undefined : executed.detail);

  if (executed.ok) {
    const out = executed.data;
    const cleared = Boolean(out.cleared);
    // A prepare-stage reversible execute legitimately STAGES the action
    // (cleared=false, performed=false, stage='prepare') — that is the prepared
    // outcome the surface shows, not a failure. A consequential execute commits
    // only when the engine cleared it (a recorded human approval).
    const staged = out.stage === 'prepare' || out.stage === 'recommend';
    const committed = cleared || (staged && !consequential);
    return ok({
      committed,
      outcome: cleared ? 'executed' : staged ? 'prepared' : 'not-performed',
      performed: Boolean(out.performed),
      cleared,
      stage: out.stage,
      reason: out.reason,
      source: 'gateway',
    });
  }

  // True infra-degrade on EXECUTE (network/timeout/5xx/unconfigured): the wall is
  // unavailable. A reversible action stages locally so the live app never breaks;
  // a consequential one cannot honestly claim it committed -> needs-approval.
  if (consequential) {
    return ok({ committed: false, outcome: 'needs-approval', source: 'fallback' });
  }
  return ok({ committed: true, outcome: 'prepared', source: 'fallback' });
}
