import { describe, it, expect } from 'vitest';
import { isRealtimeConfigured, joinChannel } from '../realtime';

describe('realtime client — degrade path (no Supabase configured)', () => {
  it('reports not configured when the public env vars are absent', () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    expect(isRealtimeConfigured()).toBe(false);
  });

  it('joinChannel resolves a no-op handle that never throws', async () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    const handle = await joinChannel({
      topic: 'msg:teacher:c1',
      self: { ref: 'opaque-self', handle: 'Teacher' },
    });
    expect(handle.live).toBe(false);
    expect(handle.presence()).toEqual([]);
    // send + leave are safe no-ops on the degraded path.
    await expect(
      handle.send({ id: 'm1', senderRef: 'opaque-self', body: 'hi', postedAt: new Date().toISOString() }),
    ).resolves.toBeUndefined();
    await expect(handle.leave()).resolves.toBeUndefined();
  });
});
