/* ============================================================================
   lib/__tests__/oauthProvider.test.ts — the social-provider mapping.

   Our auth surface offers Google, Apple, AND Microsoft. Supabase uses "azure"
   for Microsoft, so the boundary maps microsoft -> azure while keeping google
   and apple unchanged. With no Supabase configured, signInWithOAuth degrades to
   a local session whose method preserves our label (microsoft).
   ============================================================================ */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { setStoreAdapter, createMemoryAdapter, readStore } from '../store';
import { supabaseProvider, signInWithOAuth } from '../auth';
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
});

describe('supabaseProvider — maps our labels onto Supabase provider values', () => {
  it('maps microsoft -> azure', () => {
    expect(supabaseProvider('microsoft')).toBe('azure');
  });
  it('passes google and apple through unchanged', () => {
    expect(supabaseProvider('google')).toBe('google');
    expect(supabaseProvider('apple')).toBe('apple');
  });
});

describe('signInWithOAuth — microsoft degrades to a local session', () => {
  it('mints a local session whose method is microsoft', async () => {
    const result = await signInWithOAuth({ provider: 'microsoft', role: 'teacher' });
    expect(result.ok).toBe(true);
    expect(result.session?.source).toBe('local');
    expect(result.session?.method).toBe('microsoft');
    expect(readStore().account?.method).toBe('microsoft');
  });
});
