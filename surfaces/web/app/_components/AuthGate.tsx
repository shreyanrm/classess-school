'use client';

/* ============================================================================
   app/_components/AuthGate.tsx — the session gate (replaces FirstRunGate).

   The app now opens with the WELCOME preamble, then a familiar auth wall:

     - No session  -> route to /welcome (the calm preamble that introduces Vidya
       and the flow). From there: Begin -> /sign-up -> role -> a brief
       personalise -> the role home; or Sign in -> /sign-in -> the role home.
     - The welcome + auth + onboarding routes are EXEMPT so the flows can run.

   The check runs in an effect on the client only (the session resolves after
   mount; redirecting during render would loop or flash). While the first session
   read is in flight we render nothing on a gated route, so a signed-out user
   never sees a flash of the app.
   ============================================================================ */

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/useAuth';
import { useRole } from '@/lib/RoleContext';
import { readStore } from '@/lib/store';

/** Routes that must never be gated (the auth + onboarding flows). */
const EXEMPT = ['/sign-in', '/sign-up', '/forgot-password', '/reset-password', '/welcome'];

function isExempt(pathname: string): boolean {
  return EXEMPT.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() ?? '/';
  const { session, loading } = useAuth();
  const { setRole } = useRole();

  const exempt = isExempt(pathname);

  useEffect(() => {
    if (exempt || loading) return;
    if (!session) {
      router.replace('/welcome');
      return;
    }
    // A session resolved (e.g. after a restart or OAuth return): seed the active
    // role from the persisted account so the shell renders the right surface.
    const accountRole = readStore().account?.role;
    if (accountRole) setRole(accountRole);
  }, [exempt, loading, session, router, setRole]);

  // On a gated route, hold the paint until we know there is a session — so a
  // signed-out user never flashes the app before the redirect. Show a calm
  // loading affordance rather than a blank screen during the session read.
  if (!exempt && (loading || !session)) {
    return (
      <div className="auth-gate-loading" role="status" aria-live="polite">
        <span className="auth-gate-spinner" aria-hidden="true" />
        <span className="caption muted">Signing you in…</span>
      </div>
    );
  }

  return <>{children}</>;
}
