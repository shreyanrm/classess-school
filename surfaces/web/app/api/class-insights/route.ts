/* ============================================================================
   app/api/class-insights/route.ts — the CLIENT->SERVER->GATEWAY hop for the
   TEACHER loop's governed class-intelligence read (summary + per-student reads
   + the needing-attention list).

   SERVER-ONLY (runtime = 'nodejs'). The teacher surfaces (Plan / Assign /
   Evaluate / Students / Insights) are client components; the governed deep-read
   seam (lib/deepReads) is server-only because it talks to the wall. This thin
   route is the bridge: it answers with the SPINE's rolled-up class reading when
   the wall admits it, or the TS engine's faithful port (lib/classRead) when the
   wall is unreachable / denies — gateway-first, engine fallback.

     GET ?subject=<class-ref>   -> { insights, permissionDenied, source }

   The web only READS here; it never bypasses the wall. Identity is the opaque
   caller (uuid + role) from the request headers. No PII, no secret, ever
   returned. When the wall denies on RBAC/ABAC/consent the surface is told
   `permissionDenied: true` so it can render the designed permission state
   instead of silently degrading. Mirrors app/api/reads exactly.
   ============================================================================ */

import { readClassInsights, callerIdentity } from '@/lib/deepReads';
import { CLASS_REF, SEED_EVENTS, SCENARIO_NOW } from '@/lib/loopData';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const subject = (url.searchParams.get('subject') ?? CLASS_REF).trim() || CLASS_REF;

  // The opaque caller identity for the wall — uuid + role from the headers the
  // surface stamps. Never PII; falls back to the class ref / teacher role so the
  // read still resolves on the local path. The scope IS the class.
  const callerUuid = req.headers.get('x-caller-uuid') || subject;
  const role = req.headers.get('x-caller-role') || 'teacher';
  const identity = callerIdentity({ canonicalUuid: callerUuid, role, scope: subject });

  const read = await readClassInsights(subject, identity, {
    events: SEED_EVENTS,
    asof: SCENARIO_NOW,
  });

  // A wall deny on RBAC/ABAC/consent surfaces as a permission state, not a degrade.
  const permissionDenied = read.fallbackReason === 'unauthorized';

  return Response.json({
    insights: read.data,
    permissionDenied,
    source: read.source,
  });
}
