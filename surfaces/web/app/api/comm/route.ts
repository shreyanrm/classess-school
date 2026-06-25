/* ============================================================================
   app/api/comm/route.ts — the CLIENT->SERVER->GATEWAY hop for the COMMUNICATION
   capability (translate / make_tasks / ptm).

   SERVER-ONLY (runtime = 'nodejs'). The communication surfaces (Messages, the
   Parent surfaces) are client components; the wall is reached only server-side.
   This thin route is the single bridge: it takes a small, non-identifying
   request, calls the EXISTING communication capability through the wall
   (lib/gateway.callCapability -> spine gateway -> backend.dispatch -> the
   module's own logic), and answers with what the spine returned, or a clean
   degraded result when the wall is unreachable / unconfigured.

     POST { op:'translate',  text, preferredLang, sourceLang? }
     POST { op:'make_tasks', body, owner_role, title, why, ... }   (consequential)
     POST { op:'ptm',        parent_ref, child_context_ref, ... }  (consequential)

   The web only PREPARES + READS here; it never bypasses the wall and never
   re-implements the module judgment. Identity is the opaque caller (uuid + role)
   from the request headers (the same headers lib/events stamps). The approval
   token (when the surface attached one) feeds the permission ladder. No PII, no
   secret is ever returned. A wall deny surfaces as { ok:false, denied:true } so
   the surface can degrade calmly; an unreachable wall surfaces as
   { ok:false, degraded:true }.
   ============================================================================ */

import { callCapability, type CallerIdentity, type GatewayApp } from '@/lib/gateway';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** The communication operations the surfaces drive through the wall. translate
 *  is a READ; make_tasks + ptm are consequential (they emit a persisted event). */
type Op = 'translate' | 'make_tasks' | 'ptm';
const OPS: ReadonlySet<string> = new Set<Op>(['translate', 'make_tasks', 'ptm']);
const APPS: ReadonlySet<string> = new Set(['school', 'learner', 'platform']);

/** Build the opaque wall caller identity from the request headers (never PII). */
function identityFromRequest(req: Request, fallbackUuid: string): CallerIdentity {
  const uuid = (req.headers.get('x-caller-uuid') ?? '').trim() || fallbackUuid;
  const role = (req.headers.get('x-caller-role') ?? '').trim() || 'guardian';
  const scope = (req.headers.get('x-caller-scope') ?? '').trim();
  const appRaw = (req.headers.get('x-caller-app') ?? '').trim();
  const app: GatewayApp = APPS.has(appRaw) ? (appRaw as GatewayApp) : 'school';
  const auth = (req.headers.get('authorization') ?? '').trim();
  const signedToken = auth.toLowerCase().startsWith('bearer ') ? auth.slice(7).trim() : undefined;
  return {
    canonical_uuid: uuid,
    app,
    memberships: [{ app, role, scope }],
    signedToken: signedToken || undefined,
  };
}

/** translate is a cross-context read of free text into a reader's language ->
 *  assert the purpose so the wall's consent gate runs; make_tasks/ptm are
 *  consequential cross-context communication writes. */
const CONSENT_PURPOSE: Record<Op, string> = {
  translate: 'communication.translate',
  make_tasks: 'communication.message',
  ptm: 'parent_teacher_partnership',
};

export async function POST(req: Request): Promise<Response> {
  let body: Record<string, unknown>;
  try {
    body = (await req.json()) as Record<string, unknown>;
  } catch {
    return Response.json({ ok: false, degraded: true, reason: 'bad-request' }, { status: 400 });
  }

  const op = String(body.op ?? '');
  if (!OPS.has(op)) {
    return Response.json({ ok: false, degraded: true, reason: 'unknown-op' }, { status: 400 });
  }

  const subjectUuid = String(body.subject_uuid ?? body.subjectUuid ?? body.sender_ref ?? '') || 'subject';
  const identity = identityFromRequest(req, subjectUuid);
  const approvalToken = (req.headers.get('x-approval-token') ?? '').trim() || undefined;

  // The wall validates subject_uuid on every governed call. The rest of the
  // payload is the MODULE's concern (it travels to the dispatch handler, which
  // reuses translation/hub/ptm). PII-free: opaque refs + plain text only.
  const { op: _op, subjectUuid: _su, ...rest } = body;
  void _op;
  void _su;
  // The explicit, coalesced subject_uuid is authoritative (rest is spread first).
  const payload: Record<string, unknown> = { ...rest, subject_uuid: subjectUuid };

  // The capability is 'communication'; the OPERATION is the op (translate /
  // make_tasks / ptm). The dispatch registry routes these to the module's own
  // logic (translation.render_for_reader / hub.route_to_task / ptm.PtmService).
  const call = await callCapability('communication', op, {
    identity,
    payload,
    consentPurpose: CONSENT_PURPOSE[op as Op],
    approvalToken,
  });

  if (call.ok) {
    return Response.json(
      { ok: true, data: call.data, source: 'gateway' },
      { headers: { 'cache-control': 'no-store' } },
    );
  }

  // A wall deny (RBAC/ABAC/consent/approval) is a real verdict, not a degrade.
  const denied = call.reason === 'unauthorized';
  return Response.json(
    {
      ok: false,
      denied,
      degraded: !denied,
      reason: call.reason,
      detail: call.detail,
      source: 'fallback',
    },
    { status: denied ? 403 : 200, headers: { 'cache-control': 'no-store' } },
  );
}
