/* ============================================================================
   app/api/generate/route.ts — the CLIENT->SERVER->GATEWAY hop for the teacher's
   four governed GENERATE-AND-VERIFY capabilities (worksheet, lesson plan,
   session plan, course outline) + the student practice worksheet.

   SERVER-ONLY (runtime = 'nodejs'). The teacher/content surfaces are client
   components; the governed generate-and-verify seam (lib/generate) is server-only
   because it talks to the wall. This thin route is the bridge: it composes the
   board-agnostic artifact from the ontology, asks the wall to verify it, and
   answers with source='gateway' when the wall served a verified body, else
   source='fallback' (the OBSERVABLE degrade marker — never served as if live).

     GET ?op=worksheet&topic=<id>&count=5
     GET ?op=lesson-plan&topic=<id>
     GET ?op=session-plan&topic=<id>
     GET ?op=course-outline&subject=<id>

   The web only PREPARES (verify) here; nothing is published. Identity is the
   opaque caller (uuid + role) from the request headers. No PII, no secret.
   ============================================================================ */

import {
  generateWorksheet,
  generateLessonPlan,
  generateSessionPlan,
  generateCourseOutline,
} from '@/lib/generate';
import { callerIdentity } from '@/lib/deepReads';
import { CLASS_REF, MATH_SUBJECT_ID, LOOP_TOPIC_ID } from '@/lib/loopData';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(req: Request): Promise<Response> {
  const url = new URL(req.url);
  const op = (url.searchParams.get('op') ?? '').trim();
  const topic = (url.searchParams.get('topic') ?? LOOP_TOPIC_ID).trim() || LOOP_TOPIC_ID;
  const subject = (url.searchParams.get('subject') ?? MATH_SUBJECT_ID).trim() || MATH_SUBJECT_ID;
  const count = Math.max(2, Math.min(20, Number(url.searchParams.get('count')) || 5));

  // The opaque caller identity for the wall — uuid + role from the headers the
  // surface stamps. Never PII; the scope is the class. Falls back to the class
  // ref / teacher role so the verify still resolves on the local path.
  const callerUuid = req.headers.get('x-caller-uuid') || CLASS_REF;
  const role = req.headers.get('x-caller-role') || 'teacher';
  const identity = callerIdentity({ canonicalUuid: callerUuid, role, scope: subject });

  switch (op) {
    case 'worksheet': {
      const a = await generateWorksheet(topic, count, identity);
      return Response.json({ artifact: a.body, confidence: a.confidence, source: a.source });
    }
    case 'lesson-plan': {
      const a = await generateLessonPlan(topic, identity);
      return Response.json({ artifact: a.body, confidence: a.confidence, source: a.source });
    }
    case 'session-plan': {
      const a = await generateSessionPlan(topic, identity);
      return Response.json({ artifact: a.body, confidence: a.confidence, source: a.source });
    }
    case 'course-outline': {
      const a = await generateCourseOutline(subject, identity);
      return Response.json({ artifact: a.body, confidence: a.confidence, source: a.source });
    }
    default:
      return Response.json({ error: 'unknown op' }, { status: 400 });
  }
}
