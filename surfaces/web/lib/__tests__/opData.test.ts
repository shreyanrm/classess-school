import { describe, it, expect } from 'vitest';
import {
  saveSchoolLive,
  loadSchoolLive,
  saveAttendanceLive,
  saveAssignmentLive,
  saveMessageLive,
  loadMessagesLive,
  type SchoolWire,
} from '../opData';

/** A fetch stub that records the call and returns a chosen JSON body. */
function stubFetch(status: number, body: unknown) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const impl = (async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    } as Response;
  }) as unknown as typeof fetch;
  return { impl, calls };
}

const SAMPLE_SCHOOL: SchoolWire = {
  name: 'Campus North',
  board: 'Example Board',
  pacing: 'Standard',
  structure: [
    {
      id: 'g1',
      name: 'Campus North',
      grades: [{ id: 'gr1', name: 'Grade 9', sections: [{ id: 's1', name: 'Section A' }] }],
    },
  ],
  roster: [{ id: 'r1', label: 'Student A', kind: 'student', sectionId: 's1' }],
};

describe('opData client seam', () => {
  it('saveSchoolLive posts the blueprint and returns the live id', async () => {
    const { impl, calls } = stubFetch(200, { persisted: true, id: 'inst-1' });
    const res = await saveSchoolLive(SAMPLE_SCHOOL, impl);
    expect(res.persisted).toBe(true);
    expect(res.id).toBe('inst-1');
    expect(calls[0]?.url).toBe('/api/school');
    expect(calls[0]?.init?.method).toBe('POST');
    // The body must carry no secret — just the blueprint.
    expect(String(calls[0]?.init?.body)).toContain('Campus North');
  });

  it('degrades to { persisted:false } when the route reports no-db', async () => {
    const { impl } = stubFetch(200, { persisted: false, reason: 'no-db' });
    const res = await saveSchoolLive(SAMPLE_SCHOOL, impl);
    expect(res.persisted).toBe(false);
    expect(res.reason).toBe('no-db');
  });

  it('never throws on a network failure — resolves persisted:false', async () => {
    const impl = (async () => {
      throw new Error('offline');
    }) as unknown as typeof fetch;
    const res = await saveMessageLive(
      { institutionId: 'i', channelId: 'c', senderRef: 's', body: 'hi' },
      impl,
    );
    expect(res.persisted).toBe(false);
    expect(res.reason).toBe('network');
  });

  it('loadSchoolLive scopes the read by the opaque institution id', async () => {
    const { impl, calls } = stubFetch(200, { persisted: true, rows: [] });
    await loadSchoolLive('inst-42', impl);
    expect(calls[0]?.url).toContain('institution_id=inst-42');
    expect(calls[0]?.init?.method).toBe('GET');
  });

  it('loadMessagesLive scopes by channel + institution', async () => {
    const { impl, calls } = stubFetch(200, { persisted: true, rows: [{ message_id: 'm1' }] });
    const res = await loadMessagesLive('chan-1', 'inst-1', impl);
    expect(res.rows?.length).toBe(1);
    expect(calls[0]?.url).toContain('channel_id=chan-1');
    expect(calls[0]?.url).toContain('institution_id=inst-1');
  });

  it('saveAttendanceLive and saveAssignmentLive post to their routes', async () => {
    const a = stubFetch(200, { persisted: true });
    await saveAttendanceLive(
      { institutionId: 'i', sessionId: 's', marks: [{ canonicalUuid: 'u', status: 'present' }] },
      a.impl,
    );
    expect(a.calls[0]?.url).toBe('/api/attendance');

    const b = stubFetch(200, { persisted: true, id: 'asg-1' });
    const res = await saveAssignmentLive(
      { institutionId: 'i', createdBy: 't', kind: 'quick_check', title: 'Check' },
      b.impl,
    );
    expect(b.calls[0]?.url).toBe('/api/coursework');
    expect(res.id).toBe('asg-1');
  });

  it('treats a non-2xx response as not persisted (no throw)', async () => {
    const { impl } = stubFetch(400, { reason: 'invalid-input' });
    const res = await saveSchoolLive(SAMPLE_SCHOOL, impl);
    expect(res.persisted).toBe(false);
    expect(res.reason).toBe('invalid-input');
  });
});
