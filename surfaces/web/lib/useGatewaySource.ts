'use client';

/* ============================================================================
   lib/useGatewaySource.ts — the React binding for the source probe.

   The client end of /api/source-probe. A surface that renders typed FIXTURE
   data (one the spine does not yet stream as a whole object) uses this to learn
   the honest source: did the live spine answer the relevant governed read, or
   are we on the degrade fallback? It does NOT replace the fixture — it only
   tells the surface which OBSERVABLE <SourceNote source={...}/> marker to show,
   so static data is never presented as if it were live.

   It mirrors the other read hooks (useDeepReads / useParentRead): offline
   short-circuits to 'fallback' (no request attempted), the call never throws,
   and the hook re-reads when the account or the probed capability changes.
   ============================================================================ */

import { useEffect, useState } from 'react';
import { useStore } from './useStore';
import { useOnline } from './useOnline';

/** The governed capabilities a surface may probe (bounded by the route too). */
export type ProbeCapability = 'intelligence-views' | 'content' | 'learning' | 'communication';

export interface GatewaySourceState {
  /** 'gateway' when the spine answered the probe read; 'fallback' otherwise. */
  source: 'gateway' | 'fallback';
}

interface ApiBody {
  source: 'gateway' | 'fallback';
  denied?: boolean;
}

/**
 * Probe whether the live spine answers `capability` for `subject`. Returns the
 * honest source so the surface can render its fixture + the observable
 * SourceNote. Degrades to 'fallback' offline, on a route failure, or on any
 * wall decline — it never throws and never blocks the surface.
 */
export function useGatewaySource(
  capability: ProbeCapability,
  opts: { subject?: string; view?: string } = {},
): GatewaySourceState {
  const { account } = useStore();
  const online = useOnline();
  const [source, setSource] = useState<'gateway' | 'fallback'>('fallback');
  const { subject, view } = opts;

  useEffect(() => {
    if (!online) {
      setSource('fallback');
      return;
    }
    let live = true;

    const headers: Record<string, string> = {};
    if (account?.id) headers['x-caller-uuid'] = account.id;
    if (account?.role) headers['x-caller-role'] = account.role;

    const qs = new URLSearchParams({ capability });
    if (subject) qs.set('subject', subject);
    if (view) qs.set('view', view);

    fetch(`/api/source-probe?${qs.toString()}`, { headers })
      .then(async (res) => {
        if (!res.ok && res.status !== 400) throw new Error(`http-${res.status}`);
        return (await res.json()) as ApiBody;
      })
      .then((body) => {
        if (live) setSource(body.source ?? 'fallback');
      })
      .catch(() => {
        if (live) setSource('fallback');
      });

    return () => {
      live = false;
    };
  }, [capability, subject, view, account?.id, account?.role, online]);

  return { source };
}
