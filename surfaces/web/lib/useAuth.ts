'use client';

/* ============================================================================
   lib/useAuth.ts — the React binding for lib/auth.ts.

   Exposes the current AuthSession (or null), a loading flag while it resolves,
   and re-renders on any auth change (Supabase onAuthStateChange OR the local
   store subscription, bridged in lib/auth.subscribeToAuth). SSR-safe: it starts
   loading with no session and resolves after mount, so the server render and the
   first client render agree.
   ============================================================================ */

import { useEffect, useState } from 'react';
import { getSession, subscribeToAuth, authConfigured, type AuthSession } from './auth';

export interface UseAuthResult {
  session: AuthSession | null;
  /** True until the first session read resolves (avoids a sign-in flash). */
  loading: boolean;
  /** Whether real Supabase Auth is wired (false = local degrade path). */
  configured: boolean;
}

export function useAuth(): UseAuthResult {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    function refresh() {
      void getSession().then((s) => {
        if (!active) return;
        setSession(s);
        setLoading(false);
      });
    }

    refresh();
    const unsubscribe = subscribeToAuth(refresh);
    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  return { session, loading, configured: authConfigured() };
}
