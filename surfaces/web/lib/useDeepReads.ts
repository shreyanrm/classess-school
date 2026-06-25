'use client';

/* ============================================================================
   lib/useDeepReads.ts — the React binding for the governed deep-read seam.

   The student surfaces are client components; the wall lives server-side. This
   hook is the client end of the /api/reads hop: it requests the SPINE's reading
   for a set of topics (mastery + gaps), gateway-first, and the route answers
   with the engine's faithful port on degrade. The hook never throws.

   It surfaces all FIVE designed states the surface specs require:
     - loading            : the request is in flight
     - error              : the route itself failed (not a read fallback)
     - offline            : the browser is offline (no request attempted)
     - permission-denied  : the wall denied on RBAC/ABAC/consent
     - ready              : reads available (empty `reads` is the empty state)

   `source` is 'gateway' when the spine answered, 'fallback' when the engine did
   — surfaced so a surface can quietly note it is on the last-known read.
   ============================================================================ */

import { useEffect, useState } from 'react';
import { useStore } from './useStore';
import { useOnline } from './useOnline';
import type { MasteryResult, GapResult } from './engine';
import { CURRENT_STUDENT } from './loopData';

export type ReadPhase = 'loading' | 'error' | 'offline' | 'permission-denied' | 'ready';

export interface TopicRead {
  topicId: string;
  mastery: MasteryResult;
  gaps: GapResult[];
  source: 'gateway' | 'fallback';
  fallbackReason?: string;
}

export interface DeepReadsState {
  phase: ReadPhase;
  reads: TopicRead[];
  /** 'gateway' if every read was admitted by the wall; 'fallback' otherwise. */
  source: 'gateway' | 'fallback';
}

interface ApiBody {
  reads: TopicRead[];
  permissionDenied: boolean;
  source: 'gateway' | 'fallback';
}

/**
 * Read mastery + gaps for `topics` through the governed seam. Re-reads when the
 * topic set or the account changes. Offline short-circuits to the offline state
 * (the surface shows its last-known read); a route failure is the error state;
 * a wall deny is the permission-denied state.
 */
export function useDeepReads(topics: string[], subject: string = CURRENT_STUDENT.ref): DeepReadsState {
  const { account } = useStore();
  const online = useOnline();
  const [state, setState] = useState<DeepReadsState>({ phase: 'loading', reads: [], source: 'fallback' });
  const key = topics.join(',');

  useEffect(() => {
    if (!online) {
      setState((prev) => ({ ...prev, phase: 'offline' }));
      return;
    }
    if (topics.length === 0) {
      setState({ phase: 'ready', reads: [], source: 'fallback' });
      return;
    }
    let live = true;
    setState((prev) => ({ ...prev, phase: 'loading' }));

    const headers: Record<string, string> = {};
    if (account?.id) headers['x-caller-uuid'] = account.id;
    if (account?.role) headers['x-caller-role'] = account.role;

    const qs = new URLSearchParams({ topics: key, subject });
    fetch(`/api/reads?${qs.toString()}`, { headers })
      .then(async (res) => {
        if (!res.ok && res.status !== 400) throw new Error(`http-${res.status}`);
        return (await res.json()) as ApiBody;
      })
      .then((body) => {
        if (!live) return;
        if (body.permissionDenied) {
          setState({ phase: 'permission-denied', reads: body.reads ?? [], source: 'fallback' });
          return;
        }
        setState({ phase: 'ready', reads: body.reads ?? [], source: body.source ?? 'fallback' });
      })
      .catch(() => {
        if (live) setState((prev) => ({ ...prev, phase: 'error' }));
      });

    return () => {
      live = false;
    };
  }, [key, subject, account?.id, account?.role, online]);

  return state;
}
