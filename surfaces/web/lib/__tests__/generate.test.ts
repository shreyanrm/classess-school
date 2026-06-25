/* ============================================================================
   lib/__tests__/generate.test.ts — the GENERATE-AND-VERIFY seam for the four
   planning/content generators (gateway-first, ontology fallback).

   Pins the invariants:
     - COMPOSE: every artifact is composed FROM THE ONTOLOGY (board-agnostic) and
       is verified-shaped (a confidence band on every piece) either way.
     - GATEWAY-HIT: when the wall ADMITS and SERVES a verified body
       (served:true), source is 'gateway' and the band follows the wall's score.
     - DEGRADE: when the wall is unreachable / denies / cannot serve (served
       false or { ok:false }), the artifact still returns, composed locally, and
       is marked source:'fallback' — an OBSERVABLE marker, never served as live.
   ============================================================================ */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  composeWorksheet,
  composeCourseOutline,
  generateWorksheet,
  generateLessonPlan,
  generateCourseOutline,
} from '../generate';
import { callerIdentity } from '../deepReads';
import { CLASS_REF, LOOP_TOPIC_ID, MATH_SUBJECT_ID } from '../loopData';
import { GATEWAY_URL_ENV, type CallerIdentity } from '../gateway';

const SAVED_URL = process.env[GATEWAY_URL_ENV];
// The wall must be CONFIGURED for the gateway-hit path to reach the (fake) fetch;
// the client short-circuits to a clean fallback when no URL is set (the degrade).
beforeEach(() => {
  process.env[GATEWAY_URL_ENV] = 'https://wall.test';
});
afterEach(() => {
  if (SAVED_URL === undefined) delete process.env[GATEWAY_URL_ENV];
  else process.env[GATEWAY_URL_ENV] = SAVED_URL;
});

const IDENTITY: CallerIdentity = callerIdentity({
  canonicalUuid: CLASS_REF,
  role: 'teacher',
  scope: MATH_SUBJECT_ID,
});

/** A fake fetch returning a chosen status + JSON body. */
function fakeFetch(status: number, body: unknown): typeof fetch {
  return (async () =>
    ({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    }) as unknown as Response) as unknown as typeof fetch;
}

describe('generate — ontology composition (board-agnostic, verified-shaped)', () => {
  it('composes a worksheet of the requested length, each item banded', () => {
    const w = composeWorksheet(LOOP_TOPIC_ID, 5);
    expect(w.items).toHaveLength(5);
    expect(w.items.every((i) => ['high', 'middle', 'low'].includes(i.confidence))).toBe(true);
    expect(w.topicName.length).toBeGreaterThan(0);
  });

  it('composes a course outline of units -> topics -> outcomes from the ontology', () => {
    const o = composeCourseOutline(MATH_SUBJECT_ID);
    expect(o.units.length).toBeGreaterThan(0);
    expect(o.units.some((u) => u.topics.length > 0)).toBe(true);
  });
});

describe('generate — gateway-first', () => {
  it('promotes to source=gateway when the wall serves a verified body', async () => {
    const fetchImpl = fakeFetch(200, { served: true, confidence: 0.9 });
    const a = await generateWorksheet(LOOP_TOPIC_ID, 4, IDENTITY, { fetchImpl });
    expect(a.source).toBe('gateway');
    expect(a.confidence).toBe('high');
    expect(a.body.items).toHaveLength(4);
  });

  it('maps a middling wall score to a building band', async () => {
    const fetchImpl = fakeFetch(200, { served: true, confidence: 0.65 });
    const a = await generateLessonPlan(LOOP_TOPIC_ID, IDENTITY, { fetchImpl });
    expect(a.source).toBe('gateway');
    expect(a.confidence).toBe('middle');
  });
});

describe('generate — degrade marker (SourceNote fallback)', () => {
  it('falls back when the wall could not serve (served:false)', async () => {
    const fetchImpl = fakeFetch(200, { served: false, review_reason: 'no provider' });
    const a = await generateWorksheet(LOOP_TOPIC_ID, 4, IDENTITY, { fetchImpl });
    expect(a.source).toBe('fallback');
    // Still a verified-shaped artifact composed from the ontology.
    expect(a.body.items).toHaveLength(4);
  });

  it('falls back when the wall denies (403)', async () => {
    const fetchImpl = fakeFetch(403, { reason: 'rbac_denied' });
    const a = await generateCourseOutline(MATH_SUBJECT_ID, IDENTITY, { fetchImpl });
    expect(a.source).toBe('fallback');
    expect(a.body.units.length).toBeGreaterThan(0);
  });

  it('falls back when the wall is unreachable (fetch throws)', async () => {
    const a = await generateWorksheet(LOOP_TOPIC_ID, 3, IDENTITY, {
      fetchImpl: (async () => {
        throw new Error('network');
      }) as unknown as typeof fetch,
    });
    expect(a.source).toBe('fallback');
    expect(a.body.items).toHaveLength(3);
  });
});
