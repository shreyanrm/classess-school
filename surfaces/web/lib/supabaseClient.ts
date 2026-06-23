/* ============================================================================
   lib/supabaseClient.ts — the public Supabase browser client.

   The Supabase anon key + URL are PUBLIC by design (Row Level Security is the
   real wall), so they ship to the browser as NEXT_PUBLIC_* — the one documented
   exception to "secrets stay server-side". Every other secret stays server-side.

   When the two env vars are absent (the demo default), this returns null and the
   auth layer (lib/auth.ts) degrades to a local-store session, so the app always
   works without any backend provisioned.
   ============================================================================ */

import type { SupabaseClient } from '@supabase/supabase-js';

/** The public env var NAMES the live auth path needs. Browser-safe by design. */
export const SUPABASE_ENV = {
  url: 'NEXT_PUBLIC_SUPABASE_URL',
  anonKey: 'NEXT_PUBLIC_SUPABASE_ANON_KEY',
} as const;

/** Read the public Supabase URL, or undefined when unset. */
export function supabaseUrl(): string | undefined {
  return process.env.NEXT_PUBLIC_SUPABASE_URL || undefined;
}

/** Read the public Supabase anon key, or undefined when unset. */
export function supabaseAnonKey(): string | undefined {
  return process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || undefined;
}

/** True when both public env vars are present, so real Supabase Auth is wired. */
export function isSupabaseConfigured(): boolean {
  return Boolean(supabaseUrl() && supabaseAnonKey());
}

let client: SupabaseClient | null | undefined;

/**
 * The lazily-created, memoised Supabase browser client. Resolves null when the
 * public env vars are absent — callers then degrade to the local-store session.
 * The session persists in localStorage (Supabase's default), so a reload keeps
 * the user signed in.
 *
 * The SDK is loaded via a DYNAMIC import so the dependency is only resolved when
 * Supabase is actually configured. In the demo (and in tests) the env vars are
 * unset, so this returns null without ever touching '@supabase/supabase-js' —
 * which is why the app runs (and the suite passes) before the package installs.
 */
export async function getSupabaseClient(): Promise<SupabaseClient | null> {
  if (client !== undefined) return client;
  const url = supabaseUrl();
  const key = supabaseAnonKey();
  if (!url || !key) {
    client = null;
    return client;
  }
  // Resolve the SDK through an indirected specifier + @vite-ignore so the
  // bundler/test transform does NOT eagerly resolve it. The real package is
  // present at runtime once installed; in the demo/tests this branch is never
  // reached (no env vars), so the import is never attempted.
  const sdkSpecifier = '@supabase/supabase-js';
  const sdk = (await import(/* @vite-ignore */ sdkSpecifier)) as typeof import('@supabase/supabase-js');
  client = sdk.createClient(url, key, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
    },
  });
  return client;
}

/** Reset the memoised client — for tests only. */
export function __resetSupabaseClientForTests(): void {
  client = undefined;
}
