'use client';

/* ============================================================================
   lib/useSurfaceState.ts — the lightweight five-state gate for admin surfaces
   that render from the seed/contract data layer (not a governed deep read yet).

   The surface specs require every admin surface to ship the five designed read
   states (empty/loading/error/offline/permission-denied). The deep-read surfaces
   already derive their phase from a governed hook (useDeepReads / useProactive /
   useClassInsights / useGovernance). The config/ontology/network/calendar admin
   surfaces read the local seed layer, which degrades gracefully on its own — so
   this hook gives them the SAME calm states from one place without faking a
   network read:

     - offline : the browser is genuinely offline (the real signal).
     - loading : the first hydration tick — the calm skeleton, no spinner.
     - ready   : the surface renders its own content (empty is its own copy).

   `refresh` re-runs the loading tick (the retry affordance). error and
   permission-denied are reachable through the same ReadStates surface the
   moment a page wires a real governed read here.
   ============================================================================ */

import { useEffect, useState } from 'react';
import { useOnline } from './useOnline';
import type { ReadPhase } from './useDeepReads';

export interface SurfaceState {
  phase: ReadPhase;
  refresh: () => void;
}

export function useSurfaceState(): SurfaceState {
  const online = useOnline();
  const [ready, setReady] = useState(false);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    setReady(false);
    // Resolve on the next tick so the calm skeleton shows during hydration,
    // then the surface renders its own (degradable) seed content.
    const t = setTimeout(() => setReady(true), 0);
    return () => clearTimeout(t);
  }, [nonce]);

  const phase: ReadPhase = !online ? 'offline' : ready ? 'ready' : 'loading';
  return { phase, refresh: () => setNonce((n) => n + 1) };
}
