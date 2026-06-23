/* ============================================================================
   lib/supabaseAdmin.ts — the SERVER-ONLY Supabase admin (service-role) seam.

   This is the privileged counterpart to lib/supabaseClient.ts (which holds only
   the PUBLIC anon key). The SERVICE-ROLE key bypasses Row Level Security, so it
   is read ONLY here, ONLY on the server (route handlers, runtime = 'nodejs'),
   ONLY from process.env, and is NEVER logged, returned, or shipped as a
   NEXT_PUBLIC var. It is used for exactly one admin operation the surface needs:
   deleting an Auth user during right-to-erasure.

   The admin call is made over the Supabase Auth Admin REST endpoint via fetch,
   so no SDK install is required (matching the demo's no-install constraint). The
   key crosses the wire only as a Bearer / apikey header to Supabase itself.

   DEGRADE: when the service key OR the project URL is unset (the demo default)
   this resolves to "not configured" and the caller takes the clean degraded
   path. Importing this module never throws and never crashes the runtime.
   ============================================================================ */

import { supabaseUrl } from './supabaseClient';

/** The env var NAME of the server-only service-role key. Never NEXT_PUBLIC. */
export const SERVICE_KEY_ENV = 'CLSS_SUPABASE_SERVICE_ROLE_KEY' as const;

/** Read the service-role key without revealing it. Present + plausibly shaped. */
export function serviceRoleKey(): string | undefined {
  const key = process.env[SERVICE_KEY_ENV];
  return typeof key === 'string' && key.trim().length >= 8 ? key : undefined;
}

/** True when the admin path is wired (project URL + service-role key present). */
export function isAdminConfigured(): boolean {
  return Boolean(supabaseUrl() && serviceRoleKey());
}

/**
 * Delete an Auth user by id using the service-role key over the Auth Admin REST
 * endpoint. Returns true on success, false on any failure or when the admin path
 * is not configured. NEVER throws and NEVER leaks the key (it is sent only as the
 * Authorization / apikey header to Supabase, never echoed or logged).
 *
 * A fetch implementation may be injected for tests so this is exercisable without
 * a live project and without touching the network.
 */
export async function deleteAuthUser(
  userId: string,
  fetchImpl: typeof fetch = fetch,
): Promise<boolean> {
  const url = supabaseUrl();
  const key = serviceRoleKey();
  if (!url || !key) return false;

  try {
    const endpoint = `${url.replace(/\/+$/, '')}/auth/v1/admin/users/${encodeURIComponent(userId)}`;
    const res = await fetchImpl(endpoint, {
      method: 'DELETE',
      headers: {
        // The key authenticates to Supabase ONLY; it is never echoed or logged.
        authorization: `Bearer ${key}`,
        apikey: key,
      },
    });
    return res.ok;
  } catch {
    // A provider/network failure must not crash the erasure — degrade cleanly.
    return false;
  }
}
