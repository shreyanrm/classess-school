/* ============================================================================
   app/api/vidya/chat/route.ts — the autonomous Vidya TEXT route.

   SERVER-ONLY. The whole orchestrator (the SYSTEM persona, the tools, the
   tool-use loop, the permission ladder) lives in lib/vidyaServer.ts and is
   SHARED with the voice route (app/api/voice/converse). This handler is a thin
   transport: it maps the incoming {user|vidya} turns to Gemini contents, runs
   the shared turn, and returns { text, actions }. The provider key is read from
   process.env here and never returned, logged, or exposed as NEXT_PUBLIC.

   DEGRADE (no live key / provider failure): returns { degraded: true } with a
   clean 503/502 so the client falls back to the local responder.
   ============================================================================ */

import type { VidyaAction } from '@/lib/vidya';
import { KEY_ENV, runVidyaTurn, type GeminiContent } from '@/lib/vidyaServer';
import { screenText, CRISIS_SUPPORT } from '@/lib/childSafetyServer';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function degraded(reason: string, status = 503): Response {
  return Response.json({ degraded: true, reason }, { status, headers: { 'cache-control': 'no-store' } });
}

export async function POST(req: Request): Promise<Response> {
  const key = process.env[KEY_ENV];
  if (!key || key.trim().length < 16) return degraded('key-unset');

  let payload: { messages?: Array<{ role?: string; text?: string }>; role?: string };
  try {
    payload = await req.json();
  } catch {
    return degraded('bad-request', 400);
  }

  const turns = Array.isArray(payload.messages) ? payload.messages : [];
  if (turns.length === 0) return degraded('empty', 400);
  const viewerRole = payload.role ?? 'teacher';

  // CHILD-SAFETY on the live free-text path. Screen the latest human turn BEFORE
  // it reaches the tool loop. A crisis is never silenced: it short-circuits the
  // model, escalates to a human, and returns a calm supportive response rather
  // than a tutoring/navigation answer. The verdict is real, not hard-coded.
  const latestHuman = [...turns].reverse().find((t) => t.role !== 'vidya' && typeof t.text === 'string' && t.text!.trim());
  if (latestHuman?.text) {
    const screened = await screenText(latestHuman.text);
    if (screened.escalate) {
      return Response.json(
        {
          text: screened.support ?? CRISIS_SUPPORT,
          actions: [],
          safety: { escalate: true, flagged: true, category: screened.category },
        },
        { headers: { 'cache-control': 'no-store' } },
      );
    }
  }

  // Seed the conversation. Map our {user|vidya} turns to Gemini {user|model}.
  const contents: GeminiContent[] = turns
    .filter((t) => typeof t.text === 'string' && t.text.trim().length > 0)
    .map((t) => ({
      role: (t.role === 'vidya' ? 'model' : 'user') as 'user' | 'model',
      parts: [{ text: String(t.text) }],
    }));
  // Gemini requires the first content to be a user turn.
  if (contents.length === 0 || contents[0]!.role !== 'user') return degraded('empty', 400);

  const result = await runVidyaTurn(
    contents,
    key,
    `The person you are helping is in the ${viewerRole} role; shape your help and any navigation to that role.`,
  );

  if (!result.ok) return degraded('provider-error', 502);

  const text =
    result.text ||
    (result.actions.length > 0
      ? 'I have gathered what you asked for; it is shown below.'
      : 'I can help you read where the class is, prepare a check, or take you to the right page. Tell me where to start.');

  const actions: VidyaAction[] = result.actions;
  return Response.json({ text, actions }, { headers: { 'cache-control': 'no-store' } });
}
