'use client';

/* ============================================================================
   lib/useClassInsights.ts — the React binding for the TEACHER's governed
   class-intelligence read (gateway-first, engine fallback).

   The teacher loop surfaces (plan / assign / evaluate / students / insights)
   are client components; the wall lives server-side. This hook is the client
   end of the /api/class-insights hop: it requests the SPINE's rolled-up class
   reading (per-student/per-topic mastery + gaps, the summary, and the
   needing-attention list), gateway-first, and the route answers with the TS
   engine's faithful port (lib/classRead) on degrade. The hook never throws.

   It surfaces all FIVE designed states the surface specs require:
     - loading            : the request is in flight
     - error              : the route itself failed (not a read fallback)
     - offline            : the browser is offline (no request attempted)
     - permission-denied  : the wall denied on RBAC/ABAC/consent
     - ready              : insights available (empty `reads` is the empty state)

   `source` is 'gateway' when the spine answered, 'fallback' when the engine
   did — surfaced so a surface can quietly note it is on the last-known read.

   This mirrors lib/useDeepReads exactly; it is the teacher-scoped twin.
   ============================================================================ */

import { useCallback, useEffect, useState } from 'react';
import { useStore } from './useStore';
import { useOnline } from './useOnline';
import type { ClassInsights } from './deepReads';
import { CLASS_REF } from './loopData';
import type { ReadPhase } from './useDeepReads';

export type { ReadPhase } from './useDeepReads';

export interface ClassInsightsState {
  phase: ReadPhase;
  insights: ClassInsights | null;
  /** 'gateway' if the wall admitted the read; 'fallback' otherwise. */
  source: 'gateway' | 'fallback';
  /** Re-run the read (used by the error state's retry). */
  refresh: () => void;
}

interface ApiBody {
  insights: ClassInsights;
  permissionDenied: boolean;
  source: 'gateway' | 'fallback';
}

/**
 * Read the class intelligence view (summary + reads + needing-attention)
 * through the governed seam. Re-reads when the class scope or account changes.
 * Offline short-circuits to the offline state (the surface shows its last-known
 * read); a route failure is the error state; a wall deny is permission-denied.
 */
export function useClassInsights(subject: string = CLASS_REF): ClassInsightsState {
  const { account } = useStore();
  const online = useOnline();
  const [state, setState] = useState<Omit<ClassInsightsState, 'refresh'>>({
    phase: 'loading',
    insights: null,
    source: 'fallback',
  });
  const [nonce, setNonce] = useState(0);
  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (!online) {
      setState((prev) => ({ ...prev, phase: 'offline' }));
      return;
    }
    let live = true;
    setState((prev) => ({ ...prev, phase: 'loading' }));

    const headers: Record<string, string> = {};
    if (account?.id) headers['x-caller-uuid'] = account.id;
    headers['x-caller-role'] = account?.role ?? 'teacher';

    const qs = new URLSearchParams({ subject });
    fetch(`/api/class-insights?${qs.toString()}`, { headers })
      .then(async (res) => {
        if (!res.ok && res.status !== 400) throw new Error(`http-${res.status}`);
        return (await res.json()) as ApiBody;
      })
      .then((body) => {
        if (!live) return;
        if (body.permissionDenied) {
          setState({ phase: 'permission-denied', insights: body.insights ?? null, source: 'fallback' });
          return;
        }
        setState({ phase: 'ready', insights: body.insights ?? null, source: body.source ?? 'fallback' });
      })
      .catch(() => {
        if (live) setState((prev) => ({ ...prev, phase: 'error' }));
      });

    return () => {
      live = false;
    };
  }, [subject, account?.id, account?.role, online, nonce]);

  return { ...state, refresh };
}
