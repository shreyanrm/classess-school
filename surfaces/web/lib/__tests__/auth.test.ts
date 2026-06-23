/* ============================================================================
   lib/__tests__/auth.test.ts — the degraded / local-store auth path.

   With the public Supabase env vars ABSENT, lib/auth must degrade to a local
   session minted into lib/store, so sign-up / sign-in / sign-out and session
   state always work in the demo. These tests pin that behaviour and the
   non-identifying handle masking (no raw PII is ever stored).
   ============================================================================ */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import {
  setStoreAdapter,
  createMemoryAdapter,
  readStore,
} from '../store';
import {
  authConfigured,
  getSession,
  signInWithPassword,
  signUpWithPassword,
  signInWithOAuth,
  verifyPhoneOtp,
  requestPhoneOtp,
  signOut,
  maskEmail,
  localSession,
} from '../auth';
import { __resetSupabaseClientForTests } from '../supabaseClient';

const SAVED = {
  url: process.env.NEXT_PUBLIC_SUPABASE_URL,
  key: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
};

beforeEach(() => {
  // Ensure the degraded path: no Supabase configured.
  delete process.env.NEXT_PUBLIC_SUPABASE_URL;
  delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  __resetSupabaseClientForTests();
  // A clean in-memory store per test, so the local session is isolated.
  setStoreAdapter(createMemoryAdapter());
});

afterEach(() => {
  if (SAVED.url !== undefined) process.env.NEXT_PUBLIC_SUPABASE_URL = SAVED.url;
  if (SAVED.key !== undefined) process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = SAVED.key;
  __resetSupabaseClientForTests();
});

describe('auth — degraded / local path', () => {
  it('reports not configured when the public env vars are absent', () => {
    expect(authConfigured()).toBe(false);
  });

  it('starts with no session', async () => {
    expect(await getSession()).toBeNull();
    expect(localSession()).toBeNull();
  });

  it('sign-up with password mints a local session and persists it', async () => {
    const result = await signUpWithPassword({
      email: 'learner@example.com',
      password: 'a-good-password',
      role: 'student',
    });
    expect(result.ok).toBe(true);
    expect(result.session?.source).toBe('local');
    expect(result.session?.method).toBe('password');

    // The session is readable back and the role landed in the store account.
    const session = await getSession();
    expect(session).not.toBeNull();
    expect(session?.userId).toBe(result.session?.userId);
    expect(readStore().account?.role).toBe('student');
  });

  it('keeps only a masked email handle — never the raw address', async () => {
    const result = await signUpWithPassword({
      email: 'shreyan@gmail.com',
      password: 'secret-pass',
      role: 'teacher',
    });
    const handle = result.session?.handle ?? '';
    expect(handle).toBe(maskEmail('shreyan@gmail.com'));
    expect(handle).not.toContain('shreyan@gmail.com');
    // The stored account hint is the masked handle, not the raw email/password.
    const stored = JSON.stringify(readStore());
    expect(stored).not.toContain('shreyan@gmail.com');
    expect(stored).not.toContain('secret-pass');
  });

  it('sign-in with password mints a local session', async () => {
    const result = await signInWithPassword({
      email: 'a@b.com',
      password: 'pw',
      role: 'admin',
    });
    expect(result.ok).toBe(true);
    expect((await getSession())?.userId).toBe(result.session?.userId);
    expect(readStore().account?.role).toBe('admin');
  });

  it('OAuth degrades to an immediate local session', async () => {
    const result = await signInWithOAuth({ provider: 'google', role: 'parent' });
    expect(result.ok).toBe(true);
    expect(result.session?.source).toBe('local');
    expect(result.session?.method).toBe('google');
    expect((await getSession())?.method).toBe('google');
  });

  it('phone OTP degrades — request is ok and any code verifies a local session', async () => {
    const req = await requestPhoneOtp({ phone: '9876543210' });
    expect(req.ok).toBe(true);
    const result = await verifyPhoneOtp({ phone: '9876543210', code: '000000', role: 'student' });
    expect(result.ok).toBe(true);
    expect(result.session).toBeTruthy();
    // The phone digits are not stored raw — only a masked hint is kept.
    const stored = JSON.stringify(readStore());
    expect(stored).not.toContain('9876543210');
  });

  it('sign-out clears the local session', async () => {
    await signUpWithPassword({ email: 'x@y.com', password: 'pw1234', role: 'student' });
    expect(await getSession()).not.toBeNull();
    await signOut();
    expect(await getSession()).toBeNull();
    expect(localSession()).toBeNull();
  });

  it('maskEmail keeps the domain but hides the local part', () => {
    expect(maskEmail('alice@classess.io')).toBe('a•••@classess.io');
    expect(maskEmail('not-an-email')).toBe('•••');
  });
});
