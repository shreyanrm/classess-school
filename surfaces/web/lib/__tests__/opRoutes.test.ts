import { describe, it, expect, beforeEach } from 'vitest';
import { __resetPoolForTest, __setPoolForTest, type PoolLike } from '../db';
import { isUuid, str, label } from '../opRoute';
import { POST as schoolPOST, GET as schoolGET } from '../../app/api/school/route';
import { POST as attPOST, GET as attGET } from '../../app/api/attendance/route';
import { POST as cwPOST, GET as cwGET } from '../../app/api/coursework/route';
import { POST as msgPOST, GET as msgGET } from '../../app/api/messages/route';

const UUID = '11111111-1111-4111-8111-111111111111';

function jsonReq(url: string, body: unknown): Request {
  return new Request(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}

describe('opRoute helpers', () => {
  it('isUuid accepts a v4-shaped id and rejects junk', () => {
    expect(isUuid(UUID)).toBe(true);
    expect(isUuid('not-a-uuid')).toBe(false);
    expect(isUuid(42)).toBe(false);
  });
  it('str trims and coerces; label bounds length', () => {
    expect(str('  hi  ')).toBe('hi');
    expect(str(null)).toBe('');
    expect(label('x'.repeat(500), 10)).toHaveLength(10);
  });
});

describe('operational routes — degrade path (no database configured)', () => {
  beforeEach(() => {
    // No CLSS_DATABASE_URL in the test env -> getPool() resolves null.
    delete process.env.CLSS_DATABASE_URL;
    __resetPoolForTest();
  });

  it('school POST degrades to persisted:false, never throws', async () => {
    const res = await schoolPOST(jsonReq('http://t/api/school', { name: 'Campus', structure: [], roster: [] }));
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.persisted).toBe(false);
    expect(body.reason).toBe('no-db');
  });

  it('school GET degrades for a valid id', async () => {
    const res = await schoolGET(new Request(`http://t/api/school?institution_id=${UUID}`));
    const body = await res.json();
    expect(body.persisted).toBe(false);
    expect(Array.isArray(body.rows)).toBe(true);
  });

  it('attendance POST validates input before touching the db', async () => {
    const res = await attPOST(jsonReq('http://t/api/attendance', { institutionId: 'bad', sessionId: 'bad', marks: [] }));
    const body = await res.json();
    expect(res.status).toBe(400);
    expect(body.reason).toBe('invalid-input');
  });

  it('attendance POST degrades on valid input with no db', async () => {
    const res = await attPOST(jsonReq('http://t/api/attendance', { institutionId: UUID, sessionId: UUID, marks: [] }));
    const body = await res.json();
    expect(body.persisted).toBe(false);
  });

  it('coursework GET degrades; rejects a malformed id', async () => {
    const bad = await cwGET(new Request('http://t/api/coursework?institution_id=nope'));
    expect((await bad.json()).reason).toBe('invalid-input');
    const good = await cwGET(new Request(`http://t/api/coursework?institution_id=${UUID}`));
    expect((await good.json()).persisted).toBe(false);
  });

  it('messages POST validates then degrades', async () => {
    const bad = await msgPOST(jsonReq('http://t/api/messages', { institutionId: UUID, senderRef: UUID, body: '' }));
    expect((await bad.json()).reason).toBe('invalid-input');
    const good = await msgPOST(jsonReq('http://t/api/messages', { institutionId: UUID, senderRef: UUID, body: 'hi' }));
    expect((await good.json()).persisted).toBe(false);
  });

  it('messages GET degrades for a valid channel + institution', async () => {
    const res = await msgGET(new Request(`http://t/api/messages?channel_id=${UUID}&institution_id=${UUID}`));
    expect((await res.json()).persisted).toBe(false);
  });
});

describe('operational routes — live path (injected fake pool)', () => {
  beforeEach(() => {
    process.env.CLSS_DATABASE_URL = 'postgres://fake';
  });

  it('school POST persists and returns the live institution id', async () => {
    const queries: string[] = [];
    const fake: PoolLike = {
      async query<R = Record<string, unknown>>(text: string) {
        queries.push(text);
        const rows =
          text.includes('INSERT INTO operational.institutions')
            ? [{ institution_id: UUID }]
            : text.includes('RETURNING node_id')
              ? [{ node_id: UUID }]
              : [];
        return { rows: rows as R[], rowCount: rows.length };
      },
      async end() {},
    };
    __setPoolForTest(fake);

    const res = await schoolPOST(
      jsonReq('http://t/api/school', {
        name: 'Campus North',
        structure: [
          { id: 'g', name: 'Campus', grades: [{ id: 'gr', name: 'Grade 9', sections: [{ id: 's', name: 'A' }] }] },
        ],
        roster: [{ id: 'r', label: 'Student A', kind: 'student', sectionId: 's' }],
      }),
    );
    const body = await res.json();
    expect(body.persisted).toBe(true);
    expect(body.id).toBe(UUID);
    // It wrote the institution, the structure tree, and the roster.
    expect(queries.some((q) => q.includes('structure_nodes'))).toBe(true);
    expect(queries.some((q) => q.includes('memberships'))).toBe(true);
  });

  it('a write that throws is caught and reported as write-failed (never crashes)', async () => {
    const fake: PoolLike = {
      async query() {
        throw new Error('db down');
      },
      async end() {},
    };
    __setPoolForTest(fake);
    const res = await msgPOST(jsonReq('http://t/api/messages', { institutionId: UUID, senderRef: UUID, body: 'hi' }));
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.persisted).toBe(false);
    expect(body.reason).toBe('write-failed');
  });
});
