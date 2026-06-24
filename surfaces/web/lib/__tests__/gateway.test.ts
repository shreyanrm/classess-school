/* ============================================================================
   lib/__tests__/gateway.test.ts — the SERVER-ONLY gateway client + the
   gateway-first / engine-fallback deep-read seam.

   Pins the invariants that matter:
     - BUILDS + DEGRADES: with no CLSS_GATEWAY_URL the client reports unavailable
       and every call returns { ok:false, reason:'unconfigured' } (the caller
       falls back). Importing the module never throws.
     - AUTH SHAPE: the call presents an Authorization: Bearer token derived from
       the opaque session identity (canonical_uuid + role/scope) — never a raw
       secret. A session signed token is forwarded verbatim; otherwise an
       UNSIGNED dev token carrying only opaque claims is minted.
     - GATEWAY-HIT: a deep read returns gateway data when the client succeeds.
     - FALLBACK: a deep read falls back to the local engine when the client
       throws (network), times out, or is denied (401/403).
   ============================================================================ */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  callCapability,
  isGatewayAvailable,
  readCapability,
  GATEWAY_URL_ENV,
  type CallerIdentity,
} from '../gateway';
import {
  callerIdentity,
  readMastery,
  readGaps,
  readClassInsights,
} from '../deepReads';
import { computeMastery } from '../engine';
import { CURRENT_STUDENT, LOOP_TOPIC_ID, SEED_EVENTS, SCENARIO_NOW } from '../loopData';

const SAVED_URL = process.env[GATEWAY_URL_ENV];

const SUBJECT = CURRENT_STUDENT.ref;
const IDENTITY: CallerIdentity = callerIdentity({
  canonicalUuid: SUBJECT,
  role: 'teacher',
  scope: 'class-10b',
});

/** A fake fetch returning a chosen status + JSON body, capturing the request. */
function fakeFetch(
  status: number,
  body: unknown,
): { fn: typeof fetch; calls: Array<{ url: string; init: RequestInit }> } {
  const calls: Array<{ url: string; init: RequestInit }> = [];
  const fn = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    } as unknown as Response;
  }) as unknown as typeof fetch;
  return { fn, calls };
}

afterEach(() => {
  if (SAVED_URL === undefined) delete process.env[GATEWAY_URL_ENV];
  else process.env[GATEWAY_URL_ENV] = SAVED_URL;
  vi.restoreAllMocks();
});

describe('gateway client — builds + degrades', () => {
  beforeEach(() => {
    delete process.env[GATEWAY_URL_ENV];
  });

  it('reports unavailable when CLSS_GATEWAY_URL is unset', () => {
    expect(isGatewayAvailable()).toBe(false);
  });

  it('returns { ok:false, reason:"unconfigured" } with no URL — caller falls back', async () => {
    const res = await callCapability('learning', 'read', {
      identity: IDENTITY,
      payload: { subject_uuid: SUBJECT },
    });
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.reason).toBe('unconfigured');
  });

  it('reports available when CLSS_GATEWAY_URL is set', () => {
    process.env[GATEWAY_URL_ENV] = 'https://example.invalid';
    expect(isGatewayAvailable()).toBe(true);
  });
});

describe('gateway client — auth shape (opaque identity, no secret)', () => {
  beforeEach(() => {
    process.env[GATEWAY_URL_ENV] = 'https://gw.invalid';
  });

  it('presents a Bearer token and POSTs to /capabilities/{cap}/{op}', async () => {
    const { fn, calls } = fakeFetch(200, { ok: true });
    await readCapability('learning', SUBJECT, { identity: IDENTITY, view: 'mastery', fetchImpl: fn });

    expect(calls).toHaveLength(1);
    expect(calls[0]!.url).toBe('https://gw.invalid/capabilities/learning/read');
    const headers = calls[0]!.init.headers as Record<string, string>;
    const auth = headers.authorization ?? '';
    expect(auth).toMatch(/^Bearer /);
    // The minted (unsigned dev) token carries ONLY opaque claims, never a secret.
    const token = auth.replace('Bearer ', '');
    expect(token.startsWith('DEV-UNSIGNED.')).toBe(true);
    const claims = JSON.parse(
      Buffer.from(token.replace('DEV-UNSIGNED.', ''), 'base64url').toString('utf8'),
    );
    expect(claims.canonical_uuid).toBe(SUBJECT);
    expect(claims.memberships[0].role).toBe('teacher');
    expect(JSON.stringify(claims)).not.toContain('secret');
    // The read payload carries the opaque subject only.
    const sent = JSON.parse(calls[0]!.init.body as string);
    expect(sent.subject_uuid).toBe(SUBJECT);
  });

  it('forwards a session signed token verbatim (no unsigned minting)', async () => {
    const { fn, calls } = fakeFetch(200, { ok: true });
    const signed = callerIdentity({
      canonicalUuid: SUBJECT,
      role: 'teacher',
      signedToken: 'real.signed.jwt',
    });
    await readCapability('learning', SUBJECT, { identity: signed, fetchImpl: fn });
    const headers = calls[0]!.init.headers as Record<string, string>;
    expect(headers.authorization).toBe('Bearer real.signed.jwt');
  });
});

describe('deep read — gateway-hit', () => {
  beforeEach(() => {
    process.env[GATEWAY_URL_ENV] = 'https://gw.invalid';
  });

  it('readMastery returns gateway data when the wall answers a mastery object', async () => {
    const gatewayReading = {
      topicId: LOOP_TOPIC_ID,
      reading: { dimensions: {}, composite: 0.9, band: 'independent', independent: true },
      plainLanguage: 'you can do this independently',
      revisionDue: false,
      observationCount: 5,
      independentObservationCount: 4,
      evidenceEventIds: ['e1'],
      computedAt: SCENARIO_NOW,
    };
    const { fn } = fakeFetch(200, gatewayReading);
    const res = await readMastery(SUBJECT, LOOP_TOPIC_ID, IDENTITY, { fetchImpl: fn });
    expect(res.source).toBe('gateway');
    expect(res.data.plainLanguage).toBe('you can do this independently');
    expect(res.data.reading.band).toBe('independent');
  });
});

describe('deep read — fallback to the local engine', () => {
  beforeEach(() => {
    process.env[GATEWAY_URL_ENV] = 'https://gw.invalid';
  });

  it('falls back when the wall denies (401 no/invalid token)', async () => {
    const { fn } = fakeFetch(401, { error: 'denied', reason: 'no_token' });
    const res = await readMastery(SUBJECT, LOOP_TOPIC_ID, IDENTITY, { fetchImpl: fn });
    expect(res.source).toBe('fallback');
    expect(res.fallbackReason).toBe('unauthorized');
    // Identical to the local engine result.
    const local = computeMastery(SEED_EVENTS, SUBJECT, LOOP_TOPIC_ID, SCENARIO_NOW);
    expect(res.data.reading.band).toBe(local.reading.band);
    expect(res.data.plainLanguage).toBe(local.plainLanguage);
  });

  it('falls back when the wall denies (403 RBAC/ABAC)', async () => {
    const { fn } = fakeFetch(403, { error: 'denied', reason: 'rbac_denied' });
    const res = await readGaps(SUBJECT, LOOP_TOPIC_ID, IDENTITY, { fetchImpl: fn });
    expect(res.source).toBe('fallback');
    expect(Array.isArray(res.data)).toBe(true);
  });

  it('falls back when the fetch throws (network/unreachable)', async () => {
    const throwingFetch = (async () => {
      throw new Error('ECONNREFUSED');
    }) as unknown as typeof fetch;
    const res = await readClassInsights(SUBJECT, IDENTITY, { fetchImpl: throwingFetch });
    expect(res.source).toBe('fallback');
    expect(res.fallbackReason).toBe('network');
    expect(res.data.reads.length).toBeGreaterThan(0);
    expect(typeof res.data.summary.confirmed_gaps).toBe('number');
  });

  it('falls back when the wall returns a generic non-contract ack (admitted)', async () => {
    // The bare capability door returns { status:"admitted" } — not a mastery
    // object — so the shape guard rejects it and the engine answers.
    const { fn } = fakeFetch(200, { status: 'admitted', capability: 'learning', operation: 'read' });
    const res = await readMastery(SUBJECT, LOOP_TOPIC_ID, IDENTITY, { fetchImpl: fn });
    expect(res.source).toBe('fallback');
    const local = computeMastery(SEED_EVENTS, SUBJECT, LOOP_TOPIC_ID, SCENARIO_NOW);
    expect(res.data.reading.band).toBe(local.reading.band);
  });
});
