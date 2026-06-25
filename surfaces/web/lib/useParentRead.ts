'use client';

/* ============================================================================
   lib/useParentRead.ts — the React binding for the governed parent-view read.

   The parent surfaces are client components; the wall lives server-side. This
   hook is the client end of the /api/parent hop: it requests the SPINE's
   governed, consent-scoped view for the selected child, gateway-first, and the
   route answers with the typed mock bundle on degrade. The hook never throws.

   Switching child re-renders the WHOLE surface against the new child (the
   ChildSwitcher contract): the hook re-reads whenever `childId` changes.

   It surfaces all FIVE designed states the surface specs require:
     - loading            : the request is in flight
     - error              : the route itself failed (not a read fallback)
     - offline            : the browser is offline (no request attempted)
     - permission-denied  : the wall denied OR the child's view is not consented
     - ready              : the read is available (`data` may be null only when
                            consent-gated, which maps to permission-denied)

   `source` is 'gateway' when the spine answered, 'fallback' when the mock did —
   surfaced so a surface can quietly note it is on the last-known read.
   ============================================================================ */

import { useEffect, useState } from 'react';
import { useStore } from './useStore';
import { useOnline } from './useOnline';
import type { ParentChildData } from './parentData';

export type ParentReadPhase = 'loading' | 'error' | 'offline' | 'permission-denied' | 'ready';

export interface ParentReadState {
  phase: ParentReadPhase;
  data: ParentChildData | null;
  source: 'gateway' | 'fallback';
}

interface ApiBody {
  data: ParentChildData | null;
  source: 'gateway' | 'fallback';
  permissionDenied: boolean;
  consentGated: boolean;
}

/**
 * Read the selected child's governed parent view through the wall, gateway-first.
 * Re-reads when the child or the account changes. Offline short-circuits to the
 * offline state (the surface shows its last-known read); a route failure is the
 * error state; a wall deny or an unconsented child is the permission-denied
 * state (the surface renders the calm consent-gated copy there).
 */
export function useParentRead(childId: string): ParentReadState {
  const { account } = useStore();
  const online = useOnline();
  const [state, setState] = useState<ParentReadState>({
    phase: 'loading',
    data: null,
    source: 'fallback',
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

    const qs = new URLSearchParams({ child: childId });
    fetch(`/api/parent?${qs.toString()}`, { headers })
      .then(async (res) => {
        if (!res.ok) throw new Error(`http-${res.status}`);
        return (await res.json()) as ApiBody;
      })
      .then((body) => {
        if (!live) return;
        if (body.permissionDenied || body.consentGated) {
          setState({ phase: 'permission-denied', data: null, source: body.source ?? 'fallback' });
          return;
        }
        setState({ phase: 'ready', data: body.data ?? null, source: body.source ?? 'fallback' });
      })
      .catch(() => {
        if (live) setState((prev) => ({ ...prev, phase: 'error' }));
      });

    return () => {
      live = false;
    };
  }, [childId, account?.id, account?.role, online]);

  return state;
}
