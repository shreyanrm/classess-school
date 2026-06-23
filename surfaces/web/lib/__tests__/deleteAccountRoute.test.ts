/* ============================================================================
   lib/__tests__/deleteAccountRoute.test.ts — the right-to-erasure route.

   Pins the invariants that matter for app/api/account/delete:
   - VALIDATION: a malformed canonical id is rejected 400 { deleted:false } and
     never reaches the pool or the service key.
   - DEGRADE: with no CLSS_DATABASE_URL (no pool) it resolves 200
     { deleted:false, reason:'no-db' } — the demo path works; client still clears.
   - DEGRADE: with a pool but no service key it resolves { deleted:false,
     reason:'admin-unset' } and touches NOTHING.
   - HAPPY PATH: with a pool + service key it severs PII + memberships, writes ONE
     audit row, and NEVER deletes platform.events (immutability).
   - The service key is NEVER serialised into a response body.
   ============================================================================ */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { __resetPoolForTest, __setPoolForTest, type PoolLike } from '../db';
import { POST } from '../../app/api/account/delete/route';

const UUID = '22222222-2222-4222-8222-222222222222';
const SERVICE_KEY_ENV = 'CLSS_SUPABASE_SERVICE_ROLE_KEY';
const URL_ENV = 'NEXT_PUBLIC_SUPABASE_URL';

const SAVED = {
  key: process.env[SERVICE_KEY_ENV],
  url: process.env[URL_ENV],
};

function jsonReq(body: unknown): Request {
  return new Request('http://localhost/api/account/delete', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/** A recording fake pool so we can assert exactly which tables were touched. */
function recordingPool(): { pool: PoolLike; queries: string[] } {
  const queries: string[] = [];
  const pool: PoolLike = {
    async query(text: string) {
      queries.push(text);
      return { rows: [], rowCount: 0 };
    },
    async end() {},
  };
  return { pool, queries };
}

beforeEach(() => {
  delete process.env.CLSS_DATABASE_URL;
  delete process.env[SERVICE_KEY_ENV];
  delete process.env[URL_ENV];
  __resetPoolForTest();
});

afterEach(() => {
  if (SAVED.key !== undefined) process.env[SERVICE_KEY_ENV] = SAVED.key;
  if (SAVED.url !== undefined) process.env[URL_ENV] = SAVED.url;
  __resetPoolForTest();
  vi.restoreAllMocks();
});

describe('account/delete route', () => {
  it('rejects a malformed canonical id before any privileged work', async () => {
    const res = await POST(jsonReq({ canonicalUuid: 'not-a-uuid' }));
    const body = await res.json();
    expect(res.status).toBe(400);
    expect(body.deleted).toBe(false);
    expect(body.reason).toBe('invalid-input');
  });

  it('rejects a malformed JSON body cleanly', async () => {
    const res = await POST(
      new Request('http://localhost/api/account/delete', { method: 'POST', body: '{' }),
    );
    const body = await res.json();
    expect(res.status).toBe(400);
    expect(body.deleted).toBe(false);
    expect(body.reason).toBe('bad-request');
  });

  it('degrades to deleted:false reason no-db when no database is configured', async () => {
    const res = await POST(jsonReq({ canonicalUuid: UUID }));
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.deleted).toBe(false);
    expect(body.reason).toBe('no-db');
  });

  it('degrades to admin-unset when a pool exists but the service key is absent', async () => {
    const { pool, queries } = recordingPool();
    __setPoolForTest(pool);
    const res = await POST(jsonReq({ canonicalUuid: UUID }));
    const body = await res.json();
    expect(body.deleted).toBe(false);
    expect(body.reason).toBe('admin-unset');
    // Nothing was touched when the admin path is not configured.
    expect(queries).toHaveLength(0);
  });

  it('severs PII + memberships, writes ONE audit row, never deletes events', async () => {
    process.env[URL_ENV] = 'https://demo.supabase.co';
    process.env[SERVICE_KEY_ENV] = 'service-role-secret-key';
    const { pool, queries } = recordingPool();
    __setPoolForTest(pool);

    // Stub the Auth admin DELETE so no real network call is made.
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(null, { status: 200 }),
    );

    const res = await POST(jsonReq({ canonicalUuid: UUID }));
    const body = await res.json();
    expect(body.deleted).toBe(true);

    const joined = queries.join('\n');
    expect(joined).toMatch(/DELETE FROM pii_vault\.users/i);
    expect(joined).toMatch(/DELETE FROM operational\.memberships/i);
    expect(joined).toMatch(/INSERT INTO platform\.audit_log/i);
    // IMMUTABILITY: the append-only event store is never hard-deleted.
    expect(joined).not.toMatch(/DELETE FROM platform\.events/i);
    // Exactly one audit row appended.
    expect(queries.filter((q) => /INSERT INTO platform\.audit_log/i.test(q))).toHaveLength(1);

    // The service key is sent ONLY to Supabase, never echoed into the response.
    expect(JSON.stringify(body)).not.toContain('service-role-secret-key');
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('answers 405 on GET without reading any secret', async () => {
    const { GET } = await import('../../app/api/account/delete/route');
    const res = await GET();
    const body = await res.json();
    expect(res.status).toBe(405);
    expect(body.deleted).toBe(false);
    expect(body.reason).toBe('use-post');
  });
});
