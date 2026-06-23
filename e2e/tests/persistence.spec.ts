import { test, expect } from '@playwright/test';

/* ============================================================================
   persistence.spec — the live circuit: POST /api/school then GET returns the row.

   This drives the real operational seam. When CLSS_DATABASE_URL is configured
   the route persists the institution + structure tree + roster and returns a
   live institution_id; a follow-up GET ?institution_id=... must read that row
   back. When the database is NOT configured (the demo default) the route answers
   200 with { persisted: false } — so we assert the FULL round-trip when the live
   circuit is on, and assert the calm, contract-correct degrade otherwise. Either
   way the endpoint must answer cleanly and never leak a secret.
   ============================================================================ */

const SCHOOL_BODY = {
  name: 'E2E Test Campus',
  board: 'CBSE',
  pacing: 'standard',
  structure: [
    {
      id: 'g1',
      name: 'Primary',
      grades: [
        {
          id: 'gr1',
          name: 'Grade 1',
          sections: [{ id: 's1', name: 'Section A', teacherLabel: 'Teacher One' }],
        },
      ],
    },
  ],
  roster: [
    { id: 'r1', label: 'Student One', kind: 'student' as const, sectionId: 's1' },
    { id: 'r2', label: 'Teacher One', kind: 'teacher' as const, sectionId: 's1' },
  ],
};

test.describe('school persistence circuit', () => {
  test('POST /api/school then GET returns the row (or degrades cleanly)', async ({ request }) => {
    // POST the cold-start blueprint.
    const postRes = await request.post('/api/school', { data: SCHOOL_BODY });
    expect(postRes.ok(), `POST status ${postRes.status()}`).toBeTruthy();
    const posted = (await postRes.json()) as {
      persisted?: boolean;
      id?: string;
      reason?: string;
    };

    // No secret should ever come back on the wire.
    const rawPost = await postRes.text();
    expect(rawPost).not.toMatch(/CLSS_DATABASE_URL|postgres:\/\/|password=/i);

    if (!posted.persisted) {
      // Demo degrade: the contract guarantees a calm 200 with persisted:false.
      expect(posted.persisted).toBe(false);
      test.info().annotations.push({
        type: 'note',
        description: 'Live DB not configured — verified the degrade contract instead of the round-trip.',
      });
      return;
    }

    // Live circuit: an opaque institution id must come back.
    expect(posted.id, 'expected a live institution_id').toBeTruthy();
    const id = posted.id!;
    expect(id).toMatch(/^[0-9a-f-]{36}$/i);

    // GET it back, scoped to that id.
    const getRes = await request.get(`/api/school?institution_id=${encodeURIComponent(id)}`);
    expect(getRes.ok(), `GET status ${getRes.status()}`).toBeTruthy();
    const read = (await getRes.json()) as {
      persisted?: boolean;
      rows?: Array<{ institution_id: string; label: string }>;
      nodes?: unknown[];
      roster?: unknown[];
    };

    expect(read.persisted).toBe(true);
    expect(read.rows && read.rows.length, 'expected the institution row back').toBeGreaterThan(0);
    expect(read.rows![0]!.institution_id).toBe(id);
    expect(read.rows![0]!.label).toBe(SCHOOL_BODY.name);

    // The structure tree + roster should round-trip too.
    expect(Array.isArray(read.nodes)).toBeTruthy();
    expect((read.nodes ?? []).length).toBeGreaterThan(0);
    expect(Array.isArray(read.roster)).toBeTruthy();
    expect((read.roster ?? []).length).toBeGreaterThan(0);
  });

  test('GET with an invalid id is rejected with 400', async ({ request }) => {
    const res = await request.get('/api/school?institution_id=not-a-uuid');
    expect(res.status()).toBe(400);
    const body = (await res.json()) as { persisted?: boolean; reason?: string };
    expect(body.persisted).toBe(false);
  });

  test('POST without a name is rejected with 400', async ({ request }) => {
    const res = await request.post('/api/school', { data: { board: 'CBSE' } });
    expect(res.status()).toBe(400);
  });
});
