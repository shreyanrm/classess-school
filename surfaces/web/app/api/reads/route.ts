/* ============================================================================
   app/api/reads/route.ts — the CLIENT->SERVER->GATEWAY hop for the student
   loop's governed deep reads (mastery + gaps).

   SERVER-ONLY (runtime = 'nodejs'). The student surfaces (Learn / Practice /
   Progress / Work) are client components; the governed deep-read seam
   (lib/deepReads) is server-only because it talks to the wall. This thin route
   is the bridge: it takes a small, non-identifying read request and answers
   with the SPINE's reading when the wall admits it, or the TS engine's faithful
   port when the wall is unreachable / denies — gateway-first, engine fallback.

     GET ?topics=<id>,<id>&subject=<ref>   -> { reads:[{topicId, mastery, gaps,
                                                source, fallbackReason}], ... }

   The web only READS here; it never bypasses the wall. Identity is the opaque
   caller (uuid + role) from the request headers (the same headers lib/events
   stamps). No PII, no secret, ever returned. When the wall denies on RBAC/ABAC/
   consent the surface is told `permissionDenied: true` so it can render the
   designed permission state instead of silently degrading.
   ============================================================================ */

import {
  readMastery,
  readGaps,
  callerIdentity,
  type DeepRead,
} from '@/lib/deepReads';
import type { MasteryResult, GapResult } from '@/lib/engine';
import { CURRENT_STUDENT, SEED_EVENTS, SCENARIO_NOW } from '@/lib/loopData';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

interface ReadRow {
  topicId: string;
  mastery: MasteryResult;
  gaps: GapResult[];
  /** 'gateway' when the spine answered; 'fallback' when the engine did. */
  source: DeepRead<unknown>['source'];
  fallbackReason?: string;
}

/** A wall deny on RBAC/ABAC/consent surfaces as a permission state, not a degrade. */
function isDenied(reason?: string): boolean {
  return reason === 'unauthorized';
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const topics = (url.searchParams.get('topics') ?? '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 24);
  const subject = (url.searchParams.get('subject') ?? CURRENT_STUDENT.ref).trim();

  if (topics.length === 0) {
    return Response.json({ reads: [], permissionDenied: false, source: 'fallback' }, { status: 400 });
  }

  // The opaque caller identity for the wall — uuid + role from the headers the
  // surface already stamps (lib/events). Never PII; falls back to the demo
  // learner ref so the read still resolves on the local path.
  const callerUuid = req.headers.get('x-caller-uuid') || subject;
  const role = req.headers.get('x-caller-role') || 'student';
  const identity = callerIdentity({ canonicalUuid: callerUuid, role, scope: subject });

  const opts = { events: SEED_EVENTS, asof: SCENARIO_NOW };

  const reads: ReadRow[] = await Promise.all(
    topics.map(async (topicId) => {
      const [m, g] = await Promise.all([
        readMastery(subject, topicId, identity, opts),
        readGaps(subject, topicId, identity, opts),
      ]);
      return {
        topicId,
        mastery: m.data,
        gaps: g.data,
        source: m.source,
        fallbackReason: m.fallbackReason ?? g.fallbackReason,
      };
    }),
  );

  // If the wall actively denied (not merely unreachable), tell the surface so it
  // can render the permission-denied state rather than a silent fallback.
  const permissionDenied = reads.some((r) => isDenied(r.fallbackReason));
  // The honest top-level source: 'gateway' only if every read was admitted.
  const source: DeepRead<unknown>['source'] = reads.every((r) => r.source === 'gateway')
    ? 'gateway'
    : 'fallback';

  return Response.json({ reads, permissionDenied, source });
}
