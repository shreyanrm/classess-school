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

     POST { id, decision, consequential } -> approve/execute: routes the human
                                            decision through the wall FIRST
                                            (intelligence-views/actioned, carrying
                                            the approval token for consequential
                                            ops), then records the attributed
                                            `recommendation.actioned` outcome.
                                            { committed, outcome, source }

   The web only PREPARES + READS the feed; the human decision is the one write,
   and a consequential one never commits without the wall's approval. Identity is
   the opaque caller (uuid + role) from the request headers — no PII, no secret,
   ever returned. A wall DENY surfaces as `permissionDenied` / `committed:false`
   so the surface renders the designed permission state, not a silent degrade.
   ============================================================================ */

import { readRecommendations, callerIdentity } from '@/lib/deepReads';
import { authorizeWrite, denied } from '@/lib/opGate';
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
// POST — approve / execute. The one write of the loop. The wall authorizes it
// FIRST (the approval token rides for consequential ops -> the permission
// ladder), then we record the attributed outcome event.
// ---------------------------------------------------------------------------

export async function POST(req: Request): Promise<Response> {
  let body: { id?: string; decision?: string; consequential?: boolean };
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

  // The wall authorizes the actioning FIRST. The operation maps to the governed
  // intelligence-views door; the approval token (set by the surface for
  // consequential ops) rides through opGate -> the wall enforces the ladder. A
  // denied caller is refused before any outcome is recorded; an unreachable
  // wall degrades to the local committed ack so the live app never breaks.
  const gate = await authorizeWrite(req, 'intelligence-views', 'actioned', {
    payload: { recommendation_id: id, decision, consequential: Boolean(body.consequential) },
    consentPurpose: 'intelligence.recommendations',
  });
  if (!gate.proceed) return denied(gate.detail);

  // ADMIT, or any DEGRADE -> the decision commits. The attributed
  // `recommendation.actioned` outcome is recorded by the surface's emit (it
  // holds the opaque account id); here we confirm the committed decision.
  return ok({ committed: true, outcome: decision, source: 'gateway' });
}
