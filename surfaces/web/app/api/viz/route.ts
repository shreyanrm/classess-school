/* ============================================================================
   app/api/viz/route.ts — the CLIENT->SERVER->GATEWAY hop for the shared
   visualization + report reads.

   SERVER-ONLY (runtime = 'nodejs'). The viz components are client-rendered; the
   governed read seam (lib/vizReads) is server-only because it talks to the
   wall. This thin route bridges them: it takes a small, non-identifying request
   (the viz kinds + an opaque subject ref) and answers with the SPINE's reading
   when the wall admits it, or the PII-free seed when the wall is unreachable /
   denies — gateway-first, seed fallback.

     GET ?kinds=attendance,holistic&subject=<ref>
       -> { reads:[{kind, data, source, fallbackReason}], source,
            permissionDenied }

   The web only READS here; it never bypasses the wall. Identity is the opaque
   caller (uuid + role) from the request headers. No PII, no secret, ever
   returned. A wall deny surfaces as permissionDenied so the surface can render
   the designed permission state instead of silently degrading.
   ============================================================================ */

import { callerIdentity } from '@/lib/deepReads';
import { readVizBundle } from '@/lib/vizReads';
import type { VizKind } from '@/lib/vizData';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const ALL_KINDS: VizKind[] = [
  'attendance',
  'holistic',
  'formalReport',
  'rubric',
  'paper',
  'bloom',
  'success',
  'trend',
  'calendar',
  'timetable',
  'assignments',
  'testPaper',
  'teachingStats',
  'quizResult',
  'markbook',
  'paperPreview',
  'teacherPtm',
];

function parseKinds(raw: string | null): VizKind[] {
  const requested = (raw ?? '')
    .split(',')
    .map((k) => k.trim())
    .filter(Boolean);
  const valid = requested.filter((k): k is VizKind => (ALL_KINDS as string[]).includes(k));
  return valid.length > 0 ? valid : ALL_KINDS;
}

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const kinds = parseKinds(url.searchParams.get('kinds'));
  const subject = (url.searchParams.get('subject') ?? 'section-10b').trim();

  const uuid = req.headers.get('x-caller-uuid') ?? 'anon';
  const role = req.headers.get('x-caller-role') ?? 'teacher';
  const identity = callerIdentity({ canonicalUuid: uuid, role });

  const { reads, source, permissionDenied } = await readVizBundle(kinds, subject, identity);

  return Response.json({ reads, source, permissionDenied });
}
