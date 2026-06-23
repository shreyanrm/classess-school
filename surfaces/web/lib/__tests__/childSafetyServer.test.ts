/* ============================================================================
   lib/__tests__/childSafetyServer.test.ts — the safety gate.

   The gate flags a crafted harassment string and ESCALATES a crisis string. The
   no-key deterministic fallback STILL escalates a crisis (safety never depends on
   a provider being reachable). The model path can catch more but never silences
   the deterministic floor.
   ============================================================================ */

import { describe, it, expect } from 'vitest';
import {
  screenText,
  keywordVerdict,
  mergeVerdicts,
  SAFETY_KEY_ENV,
} from '../childSafetyServer';

const NO_KEY: Record<string, string | undefined> = {};
const WITH_KEY: Record<string, string | undefined> = {
  [SAFETY_KEY_ENV]: 'x'.repeat(40),
};

describe('keywordVerdict — the deterministic floor', () => {
  it('escalates a crisis / self-harm string', () => {
    const v = keywordVerdict('I want to kill myself, there is no point in living');
    expect(v.category).toBe('crisis');
    expect(v.escalate).toBe(true);
    expect(v.flagged).toBe(true);
    expect(v.allowed).toBe(false);
    expect(v.support).toBeTruthy();
  });

  it('flags (but does not escalate) a harassment string', () => {
    const v = keywordVerdict('you are worthless and everyone hates you');
    expect(v.category).toBe('harassment');
    expect(v.flagged).toBe(true);
    expect(v.escalate).toBe(false);
    expect(v.allowed).toBe(false);
  });

  it('allows ordinary school text', () => {
    const v = keywordVerdict('Could you share what to revise this weekend?');
    expect(v.category).toBe('safe');
    expect(v.allowed).toBe(true);
    expect(v.flagged).toBe(false);
    expect(v.escalate).toBe(false);
  });
});

describe('screenText — no-key fallback still catches a crisis', () => {
  it('escalates a crisis with NO key configured (deterministic floor)', async () => {
    const v = await screenText('I am going to end my life tonight', NO_KEY);
    expect(v.category).toBe('crisis');
    expect(v.escalate).toBe(true);
    expect(v.flagged).toBe(true);
    expect(v.allowed).toBe(false);
  });

  it('flags a crafted harassment string with NO key', async () => {
    const v = await screenText('go kill yourself, you pathetic loser', NO_KEY);
    expect(v.flagged).toBe(true);
    expect(v.allowed).toBe(false);
    // harassment OR crisis (the "kill yourself" threat may read as either) — both
    // hold the message; neither silences it.
    expect(['harassment', 'crisis']).toContain(v.category);
  });

  it('allows ordinary text with NO key', async () => {
    const v = await screenText('See you at the parent meeting on Friday.', NO_KEY);
    expect(v.allowed).toBe(true);
    expect(v.escalate).toBe(false);
  });
});

describe('screenText — the model can catch more, never silence the floor', () => {
  it('escalates a crisis even when the model says "safe" (floor wins)', async () => {
    // A deliberately wrong model verdict must NOT silence a real crisis the floor
    // caught. The union of both verdicts always takes the stricter one.
    const fakeFetch = (async () =>
      new Response(
        JSON.stringify({
          candidates: [{ content: { parts: [{ text: '{"category":"safe"}' }] } }],
        }),
        { status: 200 },
      )) as unknown as typeof fetch;
    const v = await screenText('I want to kill myself', WITH_KEY, fakeFetch);
    expect(v.category).toBe('crisis');
    expect(v.escalate).toBe(true);
  });

  it('catches harassment the floor missed when the model flags it', async () => {
    const fakeFetch = (async () =>
      new Response(
        JSON.stringify({
          candidates: [{ content: { parts: [{ text: '{"category":"harassment"}' }] } }],
        }),
        { status: 200 },
      )) as unknown as typeof fetch;
    // A subtly worded jibe the keyword floor would pass.
    const v = await screenText('honestly the world would be calmer without your noise', WITH_KEY, fakeFetch);
    expect(v.category).toBe('harassment');
    expect(v.flagged).toBe(true);
  });

  it('falls back to the floor when the provider fails', async () => {
    const fakeFetch = (async () => new Response('err', { status: 500 })) as unknown as typeof fetch;
    const v = await screenText('I want to die', WITH_KEY, fakeFetch);
    // Provider down: the floor still escalates the crisis.
    expect(v.category).toBe('crisis');
    expect(v.escalate).toBe(true);
  });
});

describe('mergeVerdicts — the union is the stricter verdict', () => {
  it('a crisis from either side wins', () => {
    const merged = mergeVerdicts(
      { allowed: true, flagged: false, escalate: false, category: 'safe' },
      { allowed: false, flagged: true, escalate: true, category: 'crisis' },
    );
    expect(merged.category).toBe('crisis');
    expect(merged.escalate).toBe(true);
  });
});
