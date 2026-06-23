import { describe, it, expect, vi } from 'vitest';
import { converse, encodeWav } from '../voiceConverse';

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as unknown as Response;
}

describe('converse — transport + graceful degradation', () => {
  it('returns the reply + audio on a successful turn', async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ available: true, reply: 'try a common denominator', audioBase64: 'AAA', audioMime: 'audio/wav' }),
    ) as unknown as typeof fetch;
    const res = await converse({ text: 'help' }, '/api/voice/converse', fetchImpl);
    expect(res.available).toBe(true);
    expect(res.reply).toBe('try a common denominator');
    expect(res.audioBase64).toBe('AAA');
  });

  it('parses the SAME navigate/render actions the text route returns (voice<->chat parity)', async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({
        available: true,
        reply: 'opening your mocks',
        audioBase64: null,
        actions: [
          { type: 'navigate', target: '/student/mocks', reason: 'here are your mocks' },
          { type: 'render', spec: { kind: 'mastery', topic: 'Trigonometric Ratios', plainLanguage: 'x', independent: true, revisionDue: false, observationCount: 3, dimensions: [] } },
          { type: 'navigate', target: '/not-a-real-route' }, // dropped by the defensive parser
        ],
      }),
    ) as unknown as typeof fetch;
    const res = await converse({ audioBase64: 'AAA', mimeType: 'audio/wav', role: 'student' }, '/api/voice/converse', fetchImpl);
    expect(res.available).toBe(true);
    expect(res.actions).toHaveLength(2); // the unknown target is dropped, never followed
    expect(res.actions?.[0]).toMatchObject({ type: 'navigate', target: '/student/mocks' });
    expect(res.actions?.[1]).toMatchObject({ type: 'render' });
  });

  it('degrades calmly on a 503 (no key) — never throws', async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse({ available: false, reason: 'key-unset' }, false, 503),
    ) as unknown as typeof fetch;
    const res = await converse({ text: 'help' }, '/api/voice/converse', fetchImpl);
    expect(res.available).toBe(false);
    expect(res.reason).toBe('key-unset');
  });

  it('degrades on a network error — never throws', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error('offline');
    }) as unknown as typeof fetch;
    const res = await converse({ text: 'help' }, '/api/voice/converse', fetchImpl);
    expect(res.available).toBe(false);
    expect(res.reason).toBe('network');
  });
});

describe('encodeWav — produces a valid WAV container', () => {
  it('writes a RIFF/WAVE header sized to the samples', () => {
    const sampleRate = 24000;
    const data = new Float32Array(100).fill(0.5);
    const buffer = {
      sampleRate,
      length: data.length,
      numberOfChannels: 1,
      getChannelData: () => data,
    } as unknown as AudioBuffer;
    const wav = encodeWav(buffer);
    const view = new DataView(wav);
    const tag = (off: number) =>
      String.fromCharCode(view.getUint8(off), view.getUint8(off + 1), view.getUint8(off + 2), view.getUint8(off + 3));
    expect(tag(0)).toBe('RIFF');
    expect(tag(8)).toBe('WAVE');
    expect(tag(36)).toBe('data');
    expect(view.getUint32(24, true)).toBe(sampleRate);
    expect(wav.byteLength).toBe(44 + data.length * 2);
  });
});
