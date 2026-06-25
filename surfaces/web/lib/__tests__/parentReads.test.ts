/* ============================================================================
   lib/__tests__/parentReads.test.ts — the governed parent-view read seam.

   Pins the invariants the Parent surface spec demands:
     - CONSENT FIRST: an unconsented (or unknown) child returns NO data and the
       wall is never asked — a parent sees only what consent permits.
     - GATEWAY-FIRST: a consented child's view is read through the wall; when the
       wall answers a contract-shaped bundle, that is what the surface renders.
     - DEGRADE FALLBACK: when the wall is unreachable / non-contract, the typed
       mock bundle answers, identical in shape, so the live surface never breaks.
     - PERMISSION STATE: a wall deny (401/403) surfaces `denied: true` so the
       surface renders the permission state rather than a silent degrade.
   ============================================================================ */

import { describe, it, expect, afterEach, vi } from 'vitest';
import { readParentChild, callerIdentity } from '../parentReads';
import { GATEWAY_URL_ENV } from '../gateway';
import { PARENT_CHILDREN, DEFAULT_CHILD_ID, selectChildData } from '../parentData';

const SAVED_URL = process.env[GATEWAY_URL_ENV];

const IDENTITY = callerIdentity({
  canonicalUuid: 'parent-opaque',
  role: 'guardian',
  scope: DEFAULT_CHILD_ID,
});

/** A fake fetch returning a chosen status + JSON body, capturing the calls. */
function fakeFetch(status: number, body: unknown): { fn: typeof fetch; calls: number } {
  const state = { calls: 0 };
  const fn = (async () => {
    state.calls += 1;
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    } as unknown as Response;
  }) as unknown as typeof fetch;
  return { fn, get calls() { return state.calls; } };
}

afterEach(() => {
  if (SAVED_URL === undefined) delete process.env[GATEWAY_URL_ENV];
  else process.env[GATEWAY_URL_ENV] = SAVED_URL;
  vi.restoreAllMocks();
});

describe('parent read — consent first (a parent sees only what consent permits)', () => {
  it('an unconsented child returns no data, gated, and never asks the wall', async () => {
    process.env[GATEWAY_URL_ENV] = 'https://gw.invalid';
    const gated = PARENT_CHILDREN.find((c) => !c.consentGranted)!;
    const probe = fakeFetch(200, {});
    const res = await readParentChild(gated.id, IDENTITY, { fetchImpl: probe.fn });
    expect(res.data).toBeNull();
    expect(res.consentGated).toBe(true);
    expect(res.denied).toBe(false);
    // The wall is never asked for an unconsented child — nothing to read.
    expect(probe.calls).toBe(0);
  });

  it('an unknown child returns no data and is gated', async () => {
    const res = await readParentChild('child-z', IDENTITY);
    expect(res.data).toBeNull();
    expect(res.consentGated).toBe(true);
  });
});

describe('parent read — gateway-first, mock fallback', () => {
  it('returns the gateway bundle when the wall answers a contract-shaped view', async () => {
    process.env[GATEWAY_URL_ENV] = 'https://gw.invalid';
    const gatewayBundle = {
      briefings: [{ id: 'gw-b' }],
      timeline: [],
      strengths: [],
      supportAreas: [],
      reports: [],
      learnAlongside: [],
      ptm: { scheduled: false, prep: [] },
      proof: [],
    };
    const { fn } = fakeFetch(200, gatewayBundle);
    const res = await readParentChild(DEFAULT_CHILD_ID, IDENTITY, { fetchImpl: fn });
    expect(res.source).toBe('gateway');
    expect(res.consentGated).toBe(false);
    expect(res.data?.briefings[0]?.id).toBe('gw-b');
  });

  it('falls back to the mock bundle when the wall is unreachable', async () => {
    delete process.env[GATEWAY_URL_ENV]; // unconfigured -> immediate degrade
    const res = await readParentChild(DEFAULT_CHILD_ID, IDENTITY);
    expect(res.source).toBe('fallback');
    expect(res.denied).toBe(false);
    // Identical in shape to what the surface renders directly from the mock.
    expect(res.data).toEqual(selectChildData(DEFAULT_CHILD_ID));
  });

  it('falls back when the wall answers a non-contract body (e.g. a bare ack)', async () => {
    process.env[GATEWAY_URL_ENV] = 'https://gw.invalid';
    const { fn } = fakeFetch(200, { status: 'admitted' });
    const res = await readParentChild(DEFAULT_CHILD_ID, IDENTITY, { fetchImpl: fn });
    expect(res.source).toBe('fallback');
    expect(res.data).toEqual(selectChildData(DEFAULT_CHILD_ID));
  });
});

describe('parent read — a wall deny is the permission state, not a silent degrade', () => {
  it('a 403 from the wall surfaces denied:true with the mock bundle held', async () => {
    process.env[GATEWAY_URL_ENV] = 'https://gw.invalid';
    const { fn } = fakeFetch(403, { reason: 'consent_denied' });
    const res = await readParentChild(DEFAULT_CHILD_ID, IDENTITY, { fetchImpl: fn });
    expect(res.denied).toBe(true);
    expect(res.source).toBe('fallback');
  });
});
