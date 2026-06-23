import { describe, it, expect } from 'vitest';
import {
  VoiceSession,
  httpVoiceProvider,
  type VoiceProvider,
  type VoiceTokenResult,
} from '../voice';

/** A provider that resolves a fixed result — no network, fully deterministic. */
function fakeProvider(result: VoiceTokenResult): VoiceProvider {
  return { async fetchToken() { return result; } };
}

describe('VoiceSession — graceful degrade without network', () => {
  it('starts idle with an empty transcript', () => {
    const s = new VoiceSession(fakeProvider({ ok: false, reason: 'unavailable', message: 'x' }));
    expect(s.get().state).toBe('idle');
    expect(s.get().transcript).toBe('');
    expect(s.hasToken()).toBe(false);
  });

  it('degrades to "unavailable" (not a crash) when no token is minted', async () => {
    const s = new VoiceSession(
      fakeProvider({
        ok: false,
        reason: 'unavailable',
        message: 'Voice is unavailable right now. You can keep typing to Vidya.',
      }),
    );
    const state = await s.connect();
    expect(state).toBe('unavailable');
    expect(s.get().state).toBe('unavailable');
    expect(s.get().message).toMatch(/unavailable/i);
    // Never holds a token in the degraded path.
    expect(s.hasToken()).toBe(false);
  });

  it('surfaces a transient failure as "error" with a calm retry message', async () => {
    const s = new VoiceSession(
      fakeProvider({ ok: false, reason: 'error', message: 'Voice could not start. Try again in a moment.' }),
    );
    const state = await s.connect();
    expect(state).toBe('error');
    expect(s.get().message).toMatch(/try again/i);
    expect(s.hasToken()).toBe(false);
  });

  it('moves to "listening" and holds an unexpired token on success', async () => {
    const future = new Date(Date.now() + 60_000).toISOString();
    const s = new VoiceSession(
      fakeProvider({
        ok: true,
        token: { token: 'ephemeral-abc', expiresAt: future, provider: 'gemini', model: 'gemini-live' },
      }),
    );
    const state = await s.connect();
    expect(state).toBe('listening');
    expect(s.hasToken()).toBe(true);
    // The session never exposes anything resembling a server secret — only the
    // opaque ephemeral token it was handed.
    expect(s.get()).not.toHaveProperty('token');
  });

  it('treats an expired token as no token', async () => {
    const past = new Date(Date.now() - 60_000).toISOString();
    const s = new VoiceSession(
      fakeProvider({
        ok: true,
        token: { token: 'ephemeral-old', expiresAt: past, provider: 'gemini', model: 'gemini-live' },
      }),
    );
    await s.connect();
    expect(s.hasToken()).toBe(false);
  });

  it('notifies subscribers across the lifecycle and on stop', async () => {
    const future = new Date(Date.now() + 60_000).toISOString();
    const s = new VoiceSession(
      fakeProvider({
        ok: true,
        token: { token: 'ephemeral-xyz', expiresAt: future, provider: 'gemini', model: 'gemini-live' },
      }),
    );
    const seen: string[] = [];
    const unsub = s.subscribe((snap) => seen.push(snap.state));
    await s.connect();
    s.setTranscript('what is due today');
    s.think();
    s.speak();
    s.stop();
    unsub();
    expect(seen).toContain('idle'); // initial
    expect(seen).toContain('connecting');
    expect(seen).toContain('listening');
    expect(seen).toContain('thinking');
    expect(seen).toContain('speaking');
    // stop returns to idle and clears transcript
    expect(s.get().state).toBe('idle');
    expect(s.get().transcript).toBe('');
  });

  it('only "thinks" from "listening" — guards illegal transitions', async () => {
    const s = new VoiceSession(fakeProvider({ ok: false, reason: 'unavailable', message: 'x' }));
    await s.connect(); // -> unavailable
    s.think();
    expect(s.get().state).toBe('unavailable'); // unchanged
  });
});

describe('httpVoiceProvider — maps 503 to unavailable without throwing', () => {
  it('returns "unavailable" for a 503 response', async () => {
    const provider = httpVoiceProvider('/test-voice-token');
    const original = globalThis.fetch;
    // Stub fetch to a 503 — no real network.
    globalThis.fetch = (async () =>
      new Response('voice unavailable', { status: 503 })) as typeof fetch;
    try {
      const result = await provider.fetchToken();
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.reason).toBe('unavailable');
    } finally {
      globalThis.fetch = original;
    }
  });

  it('returns "error" (never throws) when fetch rejects', async () => {
    const provider = httpVoiceProvider('/test-voice-token');
    const original = globalThis.fetch;
    globalThis.fetch = (async () => {
      throw new Error('network down');
    }) as typeof fetch;
    try {
      const result = await provider.fetchToken();
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.reason).toBe('error');
    } finally {
      globalThis.fetch = original;
    }
  });
});
