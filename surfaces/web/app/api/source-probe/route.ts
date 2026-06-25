/* ============================================================================
   app/api/source-probe/route.ts — the CLIENT->SERVER->GATEWAY hop that answers
   ONE question for a surface that renders typed fixture data: did the live spine
   answer this read, or are we on the degrade fallback?

   SERVER-ONLY (runtime = 'nodejs'). Several surfaces (the admin briefing, the
   content library, the student portfolio / work / mocks, the messages thread)
   render typed fixtures that the spine does not yet stream as a whole object.
   They must NOT present that fixture as if it were live. This thin route lets
   them attempt the relevant GOVERNED read through the wall (lib/gateway ->
   spine) and learn the honest source:

     GET ?capability=<id>&subject=<ref>[&view=<v>]  -> { source, denied }

   `source` is 'gateway' when the wall admitted a contract read, 'fallback' when
   it was unreachable / unconfigured / declined. The surface then renders its
   fixture either way, and shows the OBSERVABLE <SourceNote source={source}/> so
   the seam is never silent. The capability/view are bounded to a known set so
   the probe stays legible. No PII, no secret: opaque caller uuid + role only.
   ============================================================================ */

import { readCapability } from '@/lib/gateway';
import { callerIdentity } from '@/lib/deepReads';
import { CLASS_REF } from '@/lib/loopData';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

/** The governed capabilities a surface may probe, mapped to their consent
 *  purpose. Bounds the probe to reads the wall already authorizes. */
const PROBES: Record<string, string> = {
  // The proactive observer's intelligence the admin briefing reflects.
  'intelligence-views': 'intelligence.class-insights',
  // The content / resource library (generate-and-verify) the spine owns.
  content: 'content.library',
  // A learner's mastery/portfolio reading (student portfolio / work / mocks).
  learning: 'intelligence.mastery',
  // Cross-context family/teacher communication (the messages thread).
  communication: 'communication.translate',
};

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const capability = (url.searchParams.get('capability') ?? '').trim();
  const view = (url.searchParams.get('view') ?? '').trim() || undefined;
  const subject = (url.searchParams.get('subject') ?? CLASS_REF).trim() || CLASS_REF;

  const consentPurpose = PROBES[capability];
  if (!consentPurpose) {
    return Response.json({ source: 'fallback', denied: false, reason: 'unknown-capability' }, { status: 400 });
  }

  // The opaque caller identity for the wall — uuid + role from the headers the
  // surface stamps. Never PII; the scope IS the subject ref.
  const callerUuid = req.headers.get('x-caller-uuid') || subject;
  const role = req.headers.get('x-caller-role') || 'teacher';
  const identity = callerIdentity({ canonicalUuid: callerUuid, role, scope: subject });

  const result = await readCapability(capability, subject, { identity, view, consentPurpose });

  // A wall deny (RBAC/ABAC/consent) is a real verdict; everything else is a
  // clean degrade. Either way the surface renders its fixture + an observable
  // SourceNote — this only tells it which marker to show.
  const denied = !result.ok && result.reason === 'unauthorized';
  return Response.json(
    { source: result.ok ? 'gateway' : 'fallback', denied },
    { headers: { 'cache-control': 'no-store' } },
  );
}
