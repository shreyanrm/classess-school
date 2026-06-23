'use client';

/* ============================================================================
   app/_components/FirstRunGate.tsx — first-run routing.

   When the local store holds no account AND no institution, the app is in
   first-run and routes to /welcome. The check runs in an effect on the client
   only (the store is empty during SSR by design, so we never redirect during
   render — that would loop or flash). /welcome itself is exempt so the flow can
   run. Nothing is seeded; the empty app routes to onboarding.
   ============================================================================ */

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { isFirstRun, readStore } from '@/lib/store';

/** Paths that must never be gated (the onboarding flow itself, API). */
const EXEMPT = ['/welcome'];

export function FirstRunGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (EXEMPT.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return;
    // Read the real persisted state on the client (post-mount), then route.
    if (isFirstRun(readStore())) {
      router.replace('/welcome');
    }
  }, [pathname, router]);

  return <>{children}</>;
}
