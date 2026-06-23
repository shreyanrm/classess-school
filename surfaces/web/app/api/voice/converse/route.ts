/* ============================================================================
   app/api/voice/converse/route.ts — Vidya speech-to-speech, one turn, with
   FULL parity to the text route.

   SERVER-ONLY. Reads CLSS_AIFABRIC_DEV_GEMINI_API_KEY from process.env and
   NEVER returns it, logs it, or exposes it as a NEXT_PUBLIC var. The browser
   sends recorded audio (or text) and receives Vidya's spoken reply.

   PARITY: this route runs the SAME orchestrator as the text route — the shared
   tool-use loop, persona, and permission ladder in lib/vidyaServer.ts. A spoken
   "show my mastery", "start a quick check", or "take attendance" runs the SAME
   tools and returns the SAME navigate/render actions a typed request would, and
   obeys the SAME permission ladder (voice can only PREPARE a consequential
   action — it never auto-sends). The pipeline is:

     audio (or text) in -> runVidyaTurn (understand + tools + reply)
                        -> gemini TTS (speak the reply)
       -> { reply, audioBase64, actions } out

   The client (VoiceCapsule -> useVidya) then applies the SAME navigate
   (router.push) and render (specToInline) handling as text.

   DEGRADE (no live key / provider failure): returns { available: false } with a
   clean 503/502 so the UI degrades calmly and typing still works.

   PRODUCTION NOTE: the gateway is the wall — in production this route calls the
   AI fabric THROUGH the gateway (which holds the provider credential and runs
   generate-and-verify). This dev broker calls the provider directly server-side
   so the surface is runnable now; the key still never crosses to the client.
   ============================================================================ */

import type { VidyaAction, Role } from '@/lib/vidya';
import {
  KEY_ENV,
  runVidyaTurn,
  generateContent,
  type GeminiContent,
} from '@/lib/vidyaServer';
import { redactPII } from '@/lib/vidyaMemory';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const TTS_MODELS = ['gemini-2.5-flash-preview-tts', 'gemini-3.1-flash-tts-preview'];
const TTS_VOICE = 'Kore';

function unavailable(reason: string, status = 503): Response {
  return Response.json(
    { available: false, reason, message: 'Voice is unavailable right now. You can keep typing to Vidya.' },
    { status, headers: { 'cache-control': 'no-store' } },
  );
}

/** Wrap raw little-endian 16-bit PCM in a minimal WAV container the browser can play. */
function pcmToWav(pcm: Buffer, sampleRate: number, channels = 1, bits = 16): Buffer {
  const blockAlign = (channels * bits) >> 3;
  const byteRate = sampleRate * blockAlign;
  const header = Buffer.alloc(44);
  header.write('RIFF', 0);
  header.writeUInt32LE(36 + pcm.length, 4);
  header.write('WAVE', 8);
  header.write('fmt ', 12);
  header.writeUInt32LE(16, 16);
  header.writeUInt16LE(1, 20); // PCM
  header.writeUInt16LE(channels, 22);
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(byteRate, 28);
  header.writeUInt16LE(blockAlign, 32);
  header.writeUInt16LE(bits, 34);
  header.write('data', 36);
  header.writeUInt32LE(pcm.length, 40);
  return Buffer.concat([header, pcm]);
}

/** Parse "audio/L16;codec=pcm;rate=24000" -> 24000. Default 24k (Gemini TTS). */
function rateFromMime(mime: string | undefined): number {
  const m = /rate=(\d+)/.exec(mime ?? '');
  return m ? Number(m[1]) : 24000;
}

export async function POST(req: Request): Promise<Response> {
  const key = process.env[KEY_ENV];
  if (!key || key.trim().length < 16) return unavailable('key-unset');

  let payload: {
    text?: string;
    audioBase64?: string;
    mimeType?: string;
    role?: string;
    memoryNote?: string;
  };
  try {
    payload = await req.json();
  } catch {
    return unavailable('bad-request', 400);
  }

  // Build the user turn: inline audio (preferred) or text.
  const userPart =
    payload.audioBase64
      ? { inlineData: { mimeType: payload.mimeType || 'audio/wav', data: payload.audioBase64 } }
      : payload.text
        ? { text: payload.text }
        : null;
  if (!userPart) return unavailable('empty-turn', 400);

  const viewerRole = (payload.role ?? 'student') as Role;
  const memoryNote =
    typeof payload.memoryNote === 'string' && payload.memoryNote.trim()
      ? redactPII(payload.memoryNote).slice(0, 600)
      : '';

  // One Gemini user turn with a short framing instruction + the audio/text. The
  // shared orchestrator reasons, calls the same tools, and returns the reply +
  // navigate/render actions — identical to the text path.
  const framing = payload.audioBase64
    ? 'Listen to the learner and respond as Vidya. Use a tool if it helps answer.'
    : 'Respond as Vidya. Use a tool if it helps answer.';
  const contents: GeminiContent[] = [{ role: 'user', parts: [{ text: framing }, userPart] }];

  // Spoken replies stay short; the rendered cards carry the detail on the client.
  const turn = await runVidyaTurn(
    contents,
    key,
    'Keep the spoken reply under 60 words; let any rendered card carry the detail.',
    220,
    { role: viewerRole, memoryNote },
  );

  if (!turn.ok) {
    return unavailable(turn.status >= 400 && turn.status < 500 ? `provider ${turn.status}` : 'provider-error', 502);
  }

  const actions: VidyaAction[] = turn.actions;
  const reply: string =
    turn.text.trim() ||
    (actions.length > 0
      ? 'Here is what you asked for.'
      : 'I can help you read where you stand, prepare a check, or take you to the right place.');

  // Speak the reply. TTS is best-effort: a TTS failure still returns the text +
  // actions so the turn is never lost (the client shows the reply and acts).
  let audioBase64: string | null = null;
  try {
    const spoken = await generateContent(
      TTS_MODELS[0]!,
      {
        contents: [{ parts: [{ text: reply }] }],
        generationConfig: {
          responseModalities: ['AUDIO'],
          speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: TTS_VOICE } } },
        },
      },
      key,
    );
    let json = spoken.ok ? spoken.json : undefined;
    if (!spoken.ok && TTS_MODELS[1]) {
      const fallback = await generateContent(
        TTS_MODELS[1],
        {
          contents: [{ parts: [{ text: reply }] }],
          generationConfig: {
            responseModalities: ['AUDIO'],
            speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: TTS_VOICE } } },
          },
        },
        key,
      );
      json = fallback.ok ? fallback.json : undefined;
    }
    const audioPart = json?.candidates?.[0]?.content?.parts?.find((p: any) => p.inlineData);
    if (audioPart?.inlineData?.data) {
      const pcm = Buffer.from(audioPart.inlineData.data, 'base64');
      const wav = pcmToWav(pcm, rateFromMime(audioPart.inlineData.mimeType));
      audioBase64 = wav.toString('base64');
    }
  } catch {
    audioBase64 = null; // never leak a key or stack; the text + actions still stand.
  }

  return Response.json(
    { available: true, reply, audioBase64, audioMime: 'audio/wav', actions },
    { headers: { 'cache-control': 'no-store' } },
  );
}
