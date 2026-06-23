import { describe, it, expect, vi } from 'vitest';
import {
  makeIndependentVerifier,
  gateAction,
  claimsForAction,
  runTool,
  CROSSCHECK_KEY_ENV,
  type IndependentVerifier,
} from '../vidyaServer';
import type { VidyaAction } from '../vidya';

/* ============================================================================
   The INDEPENDENT (OpenAI) cross-check — real generate-and-verify. The factory
   picks the OpenAI verifier when the key is present and abstains when absent;
   the gate shows content only when an available model AGREES with confidence,
   withholds when it REFUTES, and falls back to deterministic-only when it
   abstains. The show_on_canvas tool withholds a derivation whose deterministic
   arithmetic check fails.
   ============================================================================ */

const KEY = 'sk-test-0123456789abcdef'; // length >= 16

function openaiResponse(body: unknown, ok = true): Response {
  return {
    ok,
    status: ok ? 200 : 500,
    json: async () => ({ choices: [{ message: { content: JSON.stringify(body) } }] }),
  } as unknown as Response;
}

const STEPS_ACTION: VidyaAction = {
  type: 'render',
  spec: {
    kind: 'steps',
    title: 'Adding fractions',
    steps: [{ text: 'A half plus a quarter is three quarters', check: { lhs: '1/2 + 1/4', rhs: '3/4' } }],
  },
};

describe('makeIndependentVerifier — factory', () => {
  it('picks the OpenAI verifier when the cross-check key is present', () => {
    const v = makeIndependentVerifier({ [CROSSCHECK_KEY_ENV]: KEY });
    expect(v.available).toBe(true);
  });

  it('abstains (falls back) when no cross-check key is configured', async () => {
    const v = makeIndependentVerifier({});
    expect(v.available).toBe(false);
    const verdict = await v.check(['anything'], 'ctx');
    expect(verdict.abstained).toBe(true);
    expect(verdict.agree).toBe(false);
  });

  it('reads the key but never returns it; calls OpenAI with a bearer token', async () => {
    const fetchImpl = vi.fn(async () => openaiResponse({ agree: true, confidence: 0.9 }));
    const v = makeIndependentVerifier(
      { [CROSSCHECK_KEY_ENV]: KEY },
      fetchImpl as unknown as typeof fetch,
    );
    const verdict = await v.check(['1/2 + 1/4 = 3/4'], 'fractions');
    expect(verdict.agree).toBe(true);
    expect(verdict.confidence).toBeCloseTo(0.9);
    // The key was sent in the Authorization header (server-side only).
    const call = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    const auth = call[1].headers as Record<string, string>;
    expect(auth.authorization).toContain('Bearer');
    // The verdict object never carries the key.
    expect(JSON.stringify(verdict)).not.toContain(KEY);
  });
});

describe('gateAction — independent agreement gates teaching content', () => {
  it('shows a derivation when the independent model agrees with confidence', async () => {
    const v: IndependentVerifier = {
      available: true,
      check: async () => ({ agree: true, confidence: 0.8, abstained: false }),
    };
    expect(await gateAction(STEPS_ACTION, v)).toBe(true);
  });

  it('withholds a derivation when the independent model REFUTES it', async () => {
    const v: IndependentVerifier = {
      available: true,
      check: async () => ({ agree: false, confidence: 0.9, abstained: false }),
    };
    expect(await gateAction(STEPS_ACTION, v)).toBe(false);
  });

  it('withholds when agreement confidence is below the threshold', async () => {
    const v: IndependentVerifier = {
      available: true,
      check: async () => ({ agree: true, confidence: 0.3, abstained: false }),
    };
    expect(await gateAction(STEPS_ACTION, v)).toBe(false);
  });

  it('falls back to deterministic-only when the verifier abstains (no key)', async () => {
    const v = makeIndependentVerifier({});
    expect(await gateAction(STEPS_ACTION, v)).toBe(true);
  });

  it('lets non-teaching actions through without a cross-check', async () => {
    const v: IndependentVerifier = {
      available: true,
      check: async () => ({ agree: false, confidence: 1, abstained: false }),
    };
    const nav: VidyaAction = { type: 'navigate', target: '/' };
    expect(claimsForAction(nav)).toBeNull();
    expect(await gateAction(nav, v)).toBe(true);
  });
});

describe('show_on_canvas tool — deterministic check withholds an unverified derivation', () => {
  it('drops a step whose arithmetic fails, keeping the verified one', () => {
    const { result, action } = runTool('show_on_canvas', {
      title: 'Adding fractions',
      content: {
        type: 'derivation',
        steps: [
          { text: 'A half plus a quarter', check: { lhs: '1/2 + 1/4', rhs: '3/4' } },
          { text: 'A wrong claim', check: { lhs: '1/2 + 1/4', rhs: '2' } },
        ],
      },
    });
    expect(result.shown).toBe(true);
    expect(action?.type).toBe('canvas');
    if (action?.type === 'canvas' && action.spec.content.type === 'derivation') {
      expect(action.spec.content.steps).toHaveLength(1);
    }
  });

  it('shows nothing when every step fails its deterministic check', () => {
    const { result, action } = runTool('show_on_canvas', {
      title: 'Bad maths',
      content: {
        type: 'derivation',
        steps: [{ text: 'wrong', check: { lhs: '1+1', rhs: '3' } }],
      },
    });
    expect(result.shown).toBe(false);
    expect(action).toBeUndefined();
  });
});
