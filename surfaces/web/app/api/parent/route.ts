/* ============================================================================
   app/api/parent/route.ts — the CLIENT->SERVER->GATEWAY hop for the Parent
   surface's governed, consent-scoped per-child read.

   SERVER-ONLY (runtime = 'nodejs'). The parent surfaces (This week / The child
   view / Reports / Together) are client components; the governed read seam
   (lib/parentReads) is server-only because it talks to the wall. This thin
   route bridges them: it takes the opaque child id and answers with the SPINE's
   governed parent view when the wall admits it, or the typed mock bundle when
   the wall is unreachable / denies — gateway-first, mock fallback.

     GET ?child=<id>  -> { data, source, permissionDenied, consentGated }

   The web only READS here; it never bypasses the wall. Identity is the opaque
   caller (uuid + role) from the request headers (the same headers lib/events
   stamps), defaulting to the guardian role. No PII, no secret, no raw score is
   ever returned. A wall deny (RBAC/ABAC/consent) surfaces as `permissionDenied`
   so the surface renders the designed permission state; an unconsented child
   surfaces as `consentGated` so it renders the calm consent-gated state.
   ============================================================================ */

import { readParentChild, callerIdentity } from '@/lib/parentReads';
import { DEFAULT_CHILD_ID } from '@/lib/parentData';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const child = (url.searchParams.get('child') ?? DEFAULT_CHILD_ID).trim();

  // The opaque caller identity for the wall — uuid + role from the headers the
  // surface already stamps (lib/events). A parent acts in the school app as a
  // guardian; the child id is the consent-scoped read subject. Never PII.
  const callerUuid = req.headers.get('x-caller-uuid') || child;
  const role = req.headers.get('x-caller-role') || 'guardian';
  const identity = callerIdentity({ canonicalUuid: callerUuid, role, scope: child });

  const result = await readParentChild(child, identity);

  return Response.json({
    data: result.data,
    source: result.source,
    permissionDenied: result.denied,
    consentGated: result.consentGated,
  });
}
