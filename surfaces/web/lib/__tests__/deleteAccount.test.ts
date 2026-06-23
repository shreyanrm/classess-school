/* ============================================================================
   lib/__tests__/deleteAccount.test.ts — the client-side erasure helper.

   deleteAccount() must ALWAYS clear local auth state (so the demo erasure path
   works without a backend), regardless of the server outcome. It also passes the
   current session's opaque canonical id to the route, and never throws.
   ============================================================================ */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setStoreAdapter, createMemoryAdapter } from '../store';
import {
  signUpWithPassword,
  getSession,
  deleteAccount,
  confirmsDeletion,
} from '../auth';
import { __resetSupabaseClientForTests } from '../supabaseClient';

const SAVED = {
  url: process.env.NEXT_PUBLIC_SUPABASE_URL,
  key: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
};

beforeEach(() => {
  delete process.env.NEXT_PUBLIC_SUPABASE_URL;
  delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  __resetSupabaseClientForTests();
  setStoreAdapter(createMemoryAdapter());
});

afterEach(() => {
  if (SAVED.url !== undefined) process.env.NEXT_PUBLIC_SUPABASE_URL = SAVED.url;
  if (SAVED.key !== undefined) process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = SAVED.key;
  __resetSupabaseClientForTests();
  vi.restoreAllMocks();
});

describe('deleteAccount — client erasure helper', () => {
  it('calls the route with the session canonical id and clears local state', async () => {
    await signUpWithPassword({ email: 'a@b.com', password: 'pw1234', role: 'student' });
    const session = await getSession();
    expect(session).not.toBeNull();

    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response(JSON.stringify({ deleted: true }), { status: 200 }));

    const result = await deleteAccount();
    expect(result.deleted).toBe(true);

    // The opaque id was sent in the body — never raw PII.
    const [, init] = fetchSpy.mock.calls[0]!;
    const sent = JSON.parse(String(init?.body));
    expect(sent.canonicalUuid).toBe(session?.userId);

    // Local session is cleared whatever the server said.
    expect(await getSession()).toBeNull();
  });

  it('still clears local state when the route is unreachable (degraded demo)', async () => {
    await signUpWithPassword({ email: 'c@d.com', password: 'pw1234', role: 'teacher' });
    expect(await getSession()).not.toBeNull();

    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('offline'));

    const result = await deleteAccount();
    expect(result.deleted).toBe(false);
    expect(result.reason).toBe('unreachable');
    expect(await getSession()).toBeNull();
  });

  it('confirm gate requires the explicit word DELETE (case-insensitive, trimmed)', () => {
    expect(confirmsDeletion('')).toBe(false);
    expect(confirmsDeletion('delet')).toBe(false);
    expect(confirmsDeletion('please delete')).toBe(false);
    expect(confirmsDeletion('DELETE')).toBe(true);
    expect(confirmsDeletion('  delete  ')).toBe(true);
    expect(confirmsDeletion('Delete')).toBe(true);
  });

  it('reports no-session and clears state when there is nothing to erase', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const result = await deleteAccount();
    expect(result.deleted).toBe(false);
    expect(result.reason).toBe('no-session');
    // No call is made when there is no session.
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(await getSession()).toBeNull();
  });
});
