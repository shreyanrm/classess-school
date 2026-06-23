/* ============================================================================
   lib/voiceConverse.ts — the browser side of Vidya speech-to-speech.

   Records a mic turn, encodes it to WAV (the format the provider accepts),
   posts it to the server broker (/api/voice/converse), and plays Vidya's spoken
   reply. The raw provider key NEVER reaches the browser — only this route does.

   Pure transport + audio encoding; all model work happens server-side.
   ============================================================================ */

import { parseActions, type VidyaAction } from './vidya';
import type { Role } from './mock';

export const CONVERSE_ROUTE = '/api/voice/converse';

export interface ConverseInput {
  audioBase64?: string;
  mimeType?: string;
  text?: string;
  /** The viewer role, so voice shapes its help and navigation like text does. */
  role?: Role;
}

export interface ConverseResult {
  available: boolean;
  reply?: string;
  audioBase64?: string | null;
  audioMime?: string;
  /** navigate/render directives — the SAME shape the text route returns. */
  actions?: VidyaAction[];
  reason?: string;
}

/** One conversational turn. Never throws on a provider/transport failure — it
 *  resolves to { available: false } so the UI degrades calmly. */
export async function converse(
  input: ConverseInput,
  route: string = CONVERSE_ROUTE,
  fetchImpl: typeof fetch = fetch,
): Promise<ConverseResult> {
  try {
    const res = await fetchImpl(route, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(input),
    });
    const data = (await res.json().catch(() => ({}))) as Partial<ConverseResult>;
    if (!res.ok || !data.available) {
      return { available: false, reason: data.reason ?? `http-${res.status}` };
    }
    return {
      available: true,
      reply: data.reply,
      audioBase64: data.audioBase64 ?? null,
      audioMime: data.audioMime ?? 'audio/wav',
      // Defensively parsed: an unknown target/spec is dropped, never followed.
      actions: parseActions((data as { actions?: unknown }).actions),
    };
  } catch {
    return { available: false, reason: 'network' };
  }
}

// --------------------------------------------------------------------------
// Mic capture + WAV encoding (browser-only; guarded so this module imports
// safely in node/tests).
// --------------------------------------------------------------------------

export function micSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof window !== 'undefined' &&
    !!(window.AudioContext || (window as any).webkitAudioContext)
  );
}

/** A live recording handle — call stop() to end and get the captured audio. */
export interface Recording {
  stop: () => Promise<Blob>;
}

export async function startRecording(): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const rec = new MediaRecorder(stream);
  const chunks: BlobPart[] = [];
  rec.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);
  rec.start();
  return {
    stop: () =>
      new Promise<Blob>((resolve) => {
        rec.onstop = () => {
          stream.getTracks().forEach((t) => t.stop());
          resolve(new Blob(chunks, { type: rec.mimeType || 'audio/webm' }));
        };
        rec.stop();
      }),
  };
}

/** Decode any recorded blob and re-encode as mono 16-bit PCM WAV, base64 —
 *  the format the provider reliably accepts across browsers. */
export async function blobToWavBase64(blob: Blob): Promise<string> {
  const Ctx = window.AudioContext || (window as any).webkitAudioContext;
  const ctx: AudioContext = new Ctx();
  try {
    const buf = await ctx.decodeAudioData(await blob.arrayBuffer());
    const wav = encodeWav(buf);
    return arrayBufferToBase64(wav);
  } finally {
    void ctx.close();
  }
}

/** Play a base64 WAV reply. Resolves when playback ends. */
export function playWavBase64(base64: string): Promise<void> {
  return new Promise((resolve) => {
    const audio = new Audio(`data:audio/wav;base64,${base64}`);
    audio.onended = () => resolve();
    audio.onerror = () => resolve();
    void audio.play().catch(() => resolve());
  });
}

// --- WAV encoder (mono, 16-bit PCM) ---------------------------------------
export function encodeWav(buffer: AudioBuffer): ArrayBuffer {
  const sampleRate = buffer.sampleRate;
  const channel = buffer.getChannelData(0); // mono mixdown via channel 0
  const out = new ArrayBuffer(44 + channel.length * 2);
  const view = new DataView(out);
  const writeStr = (off: number, s: string) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + channel.length * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeStr(36, 'data');
  view.setUint32(40, channel.length * 2, true);
  let off = 44;
  for (let i = 0; i < channel.length; i++, off += 2) {
    const s = Math.max(-1, Math.min(1, channel[i]!));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return out;
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let bin = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return typeof btoa !== 'undefined' ? btoa(bin) : Buffer.from(bin, 'binary').toString('base64');
}
