'use client';

/* ============================================================================
   lib/useVizData.ts — the React binding for the governed VIZ read seam.

   The viz + report components are pure (they take data props). This hook is the
   client end of the /api/viz hop: it requests the SPINE's reading for a set of
   viz kinds, gateway-first, and the route answers with the PII-free seed on
   degrade. The hook never throws.

   It surfaces all FIVE designed states every surface spec requires:
     - loading            : the request is in flight
     - error              : the route itself failed (not a read fallback)
     - offline            : the browser is offline (no request attempted)
     - permission-denied  : the wall denied on RBAC/ABAC/consent
     - ready              : reads available

   `source` is 'gateway' when the spine answered, 'fallback' when the seed did
   — surfaced so a surface can quietly note it is on the last-known read via
   <SourceNote source={source} />.
   ============================================================================ */

import { useEffect, useState } from 'react';
import { useStore } from './useStore';
import { useOnline } from './useOnline';
import { VIZ_FALLBACK, type VizBundle, type VizKind } from './vizData';
import type { ReadSource } from './vizReads';

export type VizPhase = 'loading' | 'error' | 'offline' | 'permission-denied' | 'ready';

export interface VizDataState {
  phase: VizPhase;
  /** The merged bundle — every requested kind, seed-filled until the read lands. */
  data: VizBundle;
  /** Per-kind source so a surface can degrade observably per-section. */
  sourceByKind: Partial<Record<VizKind, ReadSource>>;
  /** 'gateway' if every requested kind was admitted; 'fallback' otherwise. */
  source: ReadSource;
  refresh: () => void;
}

interface ApiRead {
  kind: VizKind;
  data: VizBundle[VizKind];
  source: ReadSource;
  fallbackReason?: string;
}

interface ApiBody {
  reads: ApiRead[];
  source: ReadSource;
  permissionDenied: boolean;
}

/**
 * Read the named viz `kinds` through the governed seam. Re-reads when the kind
 * set, the subject, or the account changes. Offline short-circuits to the
 * offline state (the surface shows its last-known seed); a route failure is the
 * error state; a wall deny is the permission-denied state.
 */
export function useVizData(
  kinds: VizKind[],
  subject = 'section-10b',
): VizDataState {
  const { account } = useStore();
  const online = useOnline();
  const key = kinds.join(',');
  const [tick, setTick] = useState(0);
  const [state, setState] = useState<VizDataState>({
    phase: 'loading',
    data: VIZ_FALLBACK,
    sourceByKind: {},
    source: 'fallback',
    refresh: () => setTick((t) => t + 1),
  });

  useEffect(() => {
    if (!online) {
      setState((prev) => ({ ...prev, phase: 'offline' }));
      return;
    }
    let live = true;
    setState((prev) => ({ ...prev, phase: 'loading' }));

    const headers: Record<string, string> = {};
    if (account?.id) headers['x-caller-uuid'] = account.id;
    if (account?.role) headers['x-caller-role'] = account.role;

    const qs = new URLSearchParams({ kinds: key, subject });
    fetch(`/api/viz?${qs.toString()}`, { headers })
      .then(async (res) => {
        if (!res.ok) throw new Error(`http-${res.status}`);
        return (await res.json()) as ApiBody;
      })
      .then((body) => {
        if (!live) return;
        // Merge each returned read over the seed so unrequested kinds stay safe.
        const data: VizBundle = { ...VIZ_FALLBACK };
        const sourceByKind: Partial<Record<VizKind, ReadSource>> = {};
        for (const r of body.reads ?? []) {
          (data[r.kind] as VizBundle[VizKind]) = r.data;
          sourceByKind[r.kind] = r.source;
        }
        if (body.permissionDenied) {
          setState((prev) => ({
            ...prev,
            phase: 'permission-denied',
            data,
            sourceByKind,
            source: 'fallback',
          }));
          return;
        }
        setState((prev) => ({
          ...prev,
          phase: 'ready',
          data,
          sourceByKind,
          source: body.source ?? 'fallback',
        }));
      })
      .catch(() => {
        if (live) setState((prev) => ({ ...prev, phase: 'error' }));
      });

    return () => {
      live = false;
    };
  }, [key, subject, account?.id, account?.role, online, tick]);

  return state;
}
