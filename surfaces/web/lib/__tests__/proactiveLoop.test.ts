/* ============================================================================
   lib/__tests__/proactiveLoop.test.ts — the proactive-loop CLIENT contract
   (recommend -> approve -> execute), the SHARED CONTRACT for spec 13 b11 +
   the permission ladder 11.

   Pins the three gaps this wave closed:
     - CRITICAL (opGate): a consequential WRITE that returns 4xx (401/403/404/
       unknown_*) is a REAL FAILURE -> { proceed:false }, NEVER committed. Only
       TRUE infra-degrade (network / timeout / 5xx / unconfigured) proceeds.
     - GAP#2 (deepReads.readRecommendations): uses ENGINE-DERIVED recommendations
       from the recommend rung (stable ids approve/execute resolve); falls back
       to the static list ONLY on true infra-degrade.
     - GAP#1 (route POST): after approve, calls the EXECUTE rung with the
       X-Approval-Token and surfaces the REAL execute outcome — never an echoed
       decision string.
   ============================================================================ */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { authorizeWrite } from '../opGate';
import { readRecommendations, callerIdentity } from '../deepReads';
import { GATEWAY_URL_ENV, type CallerIdentity } from '../gateway';
import { GET as proactiveGET, POST as proactivePOST } from '../../app/api/proactive/route';
import { CLASS_REF } from '../loopData';
import { RECOMMENDATIONS } from '../mock';

const SAVED_URL = process.env[GATEWAY_URL_ENV];

const IDENTITY: CallerIdentity = callerIdentity({
  canonicalUuid: CLASS_REF,
  role: 'teacher',
  scope: 'class-10b',
});

/** A fetch whose response is chosen per-call by a queue of (status, body) pairs. */
function scriptedFetch(
  script: Array<{ status: number; body: unknown }>,
): { fn: typeof fetch; urls: string[]; headers: Array<Record<string, string>> } {
  const urls: string[] = [];
  const headers: Array<Record<string, string>> = [];
  let i = 0;
  const fn = (async (url: string, init: RequestInit) => {
    urls.push(url);
    headers.push((init?.headers ?? {}) as Record<string, string>);
    const step = script[Math.min(i, script.length - 1)]!;
    i += 1;
    return {
      ok: step.status >= 200 && step.status < 300,
      status: step.status,
      json: async () => step.body,
    } as unknown as Response;
  }) as unknown as typeof fetch;
  return { fn, urls, headers };
}

function jsonReq(url: string, body: unknown, extra: Record<string, string> = {}): Request {
  return new Request(url, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-caller-uuid': CLASS_REF,
      'x-caller-role': 'teacher',
      ...extra,
    },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  process.env[GATEWAY_URL_ENV] = 'https://gw.invalid';
});
afterEach(() => {
  if (SAVED_URL === undefined) delete process.env[GATEWAY_URL_ENV];
  else process.env[GATEWAY_URL_ENV] = SAVED_URL;
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// CRITICAL — opGate.authorizeWrite: a 4xx verdict REFUSES; only infra degrades.
// ---------------------------------------------------------------------------
describe('opGate.authorizeWrite — the degrade rule', () => {
  function req(): Request {
    return jsonReq('http://t/x', {});
  }

  it('REFUSES on 401 (unauthorized) — never committed', async () => {
    const { fn } = scriptedFetch([{ status: 401, body: { reason: 'no_token' } }]);
    const gate = await authorizeWrite(req(), 'messages', 'send', { fetchImpl: fn });
    expect(gate.proceed).toBe(false);
  });

  it('REFUSES on 403 (RBAC/ABAC/approval denied) — never committed', async () => {
    const { fn } = scriptedFetch([{ status: 403, body: { reason: 'approval_required' } }]);
    const gate = await authorizeWrite(req(), 'messages', 'send', { fetchImpl: fn });
    expect(gate.proceed).toBe(false);
  });

  it('REFUSES on 404 / unknown_* — a write the wall could not resolve is NOT committed', async () => {
    const { fn } = scriptedFetch([{ status: 404, body: { error: 'unknown_recommendation' } }]);
    const gate = await authorizeWrite(req(), 'intelligence-views', 'execute', { fetchImpl: fn });
    expect(gate.proceed).toBe(false);
  });

  it('REFUSES on other 4xx (409/422) — fail closed', async () => {
    const { fn } = scriptedFetch([{ status: 422, body: { error: 'bad' } }]);
    const gate = await authorizeWrite(req(), 'coursework', 'submit', { fetchImpl: fn });
    expect(gate.proceed).toBe(false);
  });

  it('PROCEEDS on a 5xx (true infra-degrade) so the live app never breaks', async () => {
    const { fn } = scriptedFetch([{ status: 503, body: {} }]);
    const gate = await authorizeWrite(req(), 'messages', 'send', { fetchImpl: fn });
    expect(gate.proceed).toBe(true);
  });

  it('PROCEEDS on a network error (true infra-degrade)', async () => {
    const fn = (async () => {
      throw new Error('ECONNREFUSED');
    }) as unknown as typeof fetch;
    const gate = await authorizeWrite(req(), 'messages', 'send', { fetchImpl: fn });
    expect(gate.proceed).toBe(true);
  });

  it('PROCEEDS on an ADMIT (2xx)', async () => {
    const { fn } = scriptedFetch([{ status: 200, body: { status: 'admitted' } }]);
    const gate = await authorizeWrite(req(), 'messages', 'send', { fetchImpl: fn });
    expect(gate.proceed).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// GAP#2 — readRecommendations uses ENGINE-DERIVED ids, falls back only on infra.
// ---------------------------------------------------------------------------
describe('deepReads.readRecommendations — engine-derived stable ids', () => {
  it('adopts the engine recommendation_id the recommend rung minted', async () => {
    const { fn, urls } = scriptedFetch([
      { status: 200, body: { dispatched: true, recommendation_id: 'eng-1', is_consequential: false } },
      { status: 200, body: { dispatched: true, recommendation_id: 'eng-2', is_consequential: true } },
    ]);
    const read = await readRecommendations(CLASS_REF, IDENTITY, { fetchImpl: fn });
    expect(read.source).toBe('gateway');
    expect(read.data.map((r) => r.id)).toEqual(['eng-1', 'eng-2']);
    // It hit the RECOMMEND rung, not a generic read.
    expect(urls.every((u) => u.includes('/intelligence-views/recommend'))).toBe(true);
  });

  it('falls back to the static list ONLY on true infra-degrade (network)', async () => {
    const fn = (async () => {
      throw new Error('offline');
    }) as unknown as typeof fetch;
    const read = await readRecommendations(CLASS_REF, IDENTITY, { fetchImpl: fn });
    expect(read.source).toBe('fallback');
    expect(read.data.map((r) => r.id)).toEqual(RECOMMENDATIONS.map((r) => r.id));
  });

  it('a wall DENY surfaces the permission state (fallbackReason unauthorized), not a silent mock', async () => {
    const { fn } = scriptedFetch([{ status: 403, body: { reason: 'rbac_denied' } }]);
    const read = await readRecommendations(CLASS_REF, IDENTITY, { fetchImpl: fn });
    expect(read.fallbackReason).toBe('unauthorized');
  });
});

// ---------------------------------------------------------------------------
// GAP#1 — the route POST chains approve -> execute, returns the REAL outcome.
// ---------------------------------------------------------------------------
describe('proactive route POST — approve + execute with the approval token', () => {
  it('consequential approve -> execute returns the REAL cleared outcome (never the decision)', async () => {
    const { fn, urls, headers } = scriptedFetch([
      { status: 200, body: { dispatched: true, operation: 'approve', cleared: true } },
      {
        status: 200,
        body: { dispatched: true, operation: 'execute', cleared: true, performed: false, stage: 'execute_with_permission' },
      },
    ]);
    // Inject the scripted fetch via the global (the route uses global fetch).
    vi.stubGlobal('fetch', fn);
    const res = await proactivePOST(
      jsonReq('http://t/api/proactive', { id: 'eng-2', decision: 'approve', consequential: true }),
    );
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.committed).toBe(true);
    expect(body.outcome).toBe('executed'); // the REAL outcome, NOT 'approve'
    expect(body.cleared).toBe(true);
    // It hit APPROVE then EXECUTE.
    expect(urls[0]).toContain('/intelligence-views/approve');
    expect(urls[1]).toContain('/intelligence-views/execute');
    // The EXECUTE rung carried the X-Approval-Token (the permission ladder).
    expect(headers[1]?.['X-Approval-Token']).toBeTruthy();
  });

  it('a 404 (unknown id) on approve REFUSES — committed:false, never an echoed decision', async () => {
    const { fn } = scriptedFetch([{ status: 404, body: { error: 'unknown_recommendation' } }]);
    vi.stubGlobal('fetch', fn);
    const res = await proactivePOST(
      jsonReq('http://t/api/proactive', { id: 'ghost', decision: 'approve', consequential: true }),
    );
    const body = await res.json();
    expect(res.status).toBe(403);
    expect(body.persisted).toBe(false);
    expect(body.sent).toBe(false);
  });

  it('a reversible execute returns the staged outcome (prepare), committed', async () => {
    const { fn, urls } = scriptedFetch([
      {
        status: 200,
        body: { dispatched: true, operation: 'execute', cleared: false, performed: false, stage: 'prepare' },
      },
    ]);
    vi.stubGlobal('fetch', fn);
    const res = await proactivePOST(
      jsonReq('http://t/api/proactive', { id: 'eng-1', decision: 'execute', consequential: false }),
    );
    const body = await res.json();
    expect(body.committed).toBe(true);
    expect(body.outcome).toBe('prepared');
    expect(urls[0]).toContain('/intelligence-views/execute');
  });

  it('decline never commits', async () => {
    const res = await proactivePOST(
      jsonReq('http://t/api/proactive', { id: 'eng-1', decision: 'decline' }),
    );
    const body = await res.json();
    expect(body.committed).toBe(false);
    expect(body.outcome).toBe('declined');
  });
});

// ---------------------------------------------------------------------------
// GET — recommend feed surfaces the engine ids / permission state.
// ---------------------------------------------------------------------------
describe('proactive route GET — the recommend feed', () => {
  it('returns engine-derived ids when the recommend rung answers', async () => {
    const { fn } = scriptedFetch([
      { status: 200, body: { dispatched: true, recommendation_id: 'eng-a', is_consequential: false } },
      { status: 200, body: { dispatched: true, recommendation_id: 'eng-b', is_consequential: true } },
    ]);
    vi.stubGlobal('fetch', fn);
    const res = await proactiveGET(
      new Request('http://t/api/proactive', { headers: { 'x-caller-uuid': CLASS_REF, 'x-caller-role': 'teacher' } }),
    );
    const body = await res.json();
    expect(body.permissionDenied).toBe(false);
    expect(body.source).toBe('gateway');
    expect(body.recommendations.map((r: { id: string }) => r.id)).toEqual(['eng-a', 'eng-b']);
  });

  it('surfaces permissionDenied on a wall DENY', async () => {
    const { fn } = scriptedFetch([{ status: 403, body: { reason: 'rbac_denied' } }]);
    vi.stubGlobal('fetch', fn);
    const res = await proactiveGET(
      new Request('http://t/api/proactive', { headers: { 'x-caller-uuid': CLASS_REF, 'x-caller-role': 'teacher' } }),
    );
    const body = await res.json();
    expect(body.permissionDenied).toBe(true);
  });
});
