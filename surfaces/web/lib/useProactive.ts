'use client';

/* ============================================================================
   lib/useProactive.ts — the React binding for the proactive loop (recommend ->
   approve -> execute), spec 13 b11 + the permission ladder 11.

   The home chips, the /proactive page, and Vidya's recommendations are client
   surfaces; the wall lives server-side. This hook is the client end of the
   /api/proactive hop: it READS the recommendation feed gateway-first (the route
   answers with the spine's recommendations, or the local list on degrade), and
   it POSTs the human's approve/execute/decline decision (the one write of the
   loop, authorized at the wall, never committed on its own for consequential
   actions). The hook never throws.

   It surfaces all FIVE designed states the surface specs require:
     - loading            : the recommend read is in flight
     - error              : the route itself failed
     - offline            : the browser is offline (no request attempted)
     - permission-denied  : the wall denied on RBAC/ABAC/consent
     - ready              : the feed is available (empty list is the empty state)

   `source` is 'gateway' when the spine answered, 'fallback' when the local list
   did — surfaced so a surface can quietly note it is on the last-known feed.
   ============================================================================ */

import { useCallback, useEffect, useState } from 'react';
import { useStore } from './useStore';
import { useOnline } from './useOnline';
import type { Recommendation } from './mock';

export type ProactivePhase = 'loading' | 'error' | 'offline' | 'permission-denied' | 'ready';

export type ProactiveSource = 'gateway' | 'fallback';

/** The committed outcome of a human decision on a recommendation. */
export type Decision = 'approve' | 'execute' | 'decline';

export interface ActionResult {
  committed: boolean;
  /** The REAL execute outcome from the loop ('executed' | 'prepared' |
   *  'not-performed' | 'needs-approval' | 'declined') — never an echoed decision. */
  outcome?: string;
  /** A wall deny / unresolved 4xx (a consequential op without approval) -> not committed. */
  denied?: boolean;
  /** True when the engine actually cleared the consequential action. */
  cleared?: boolean;
  /** The ladder stage the execute rung resolved at (e.g. 'prepare'). */
  stage?: string;
  source?: ProactiveSource;
}

export interface ProactiveState {
  phase: ProactivePhase;
  recommendations: Recommendation[];
  source: ProactiveSource;
}

interface FeedBody {
  recommendations: Recommendation[];
  permissionDenied: boolean;
  source: ProactiveSource;
}

function callerHeaders(account: { id?: string; role?: string } | null): Record<string, string> {
  const headers: Record<string, string> = {};
  if (account?.id) headers['x-caller-uuid'] = account.id;
  if (account?.role) headers['x-caller-role'] = account.role;
  return headers;
}

/**
 * Read the proactive feed through the governed seam and expose the loop's one
 * write — `actioned(id, decision, consequential)`. Re-reads when the account
 * changes or online flips back. Offline short-circuits to the offline state.
 */
export function useProactive(subject?: string): ProactiveState & {
  /** Re-run the recommend read (e.g. a manual retry from the error state). */
  refresh: () => void;
  /**
   * Commit a human decision on a recommendation. `consequential` ones carry the
   * approval token at the wall (the permission ladder); reversible ones execute
   * directly. Never throws — a wall deny resolves to { committed:false, denied }.
   */
  actioned: (id: string, decision: Decision, consequential?: boolean) => Promise<ActionResult>;
} {
  const { account } = useStore();
  const online = useOnline();
  const [state, setState] = useState<ProactiveState>({
    phase: 'loading',
    recommendations: [],
    source: 'fallback',
  });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!online) {
      setState((prev) => ({ ...prev, phase: 'offline' }));
      return;
    }
    let live = true;
    setState((prev) => ({ ...prev, phase: 'loading' }));

    const qs = subject ? `?subject=${encodeURIComponent(subject)}` : '';
    fetch(`/api/proactive${qs}`, { headers: callerHeaders(account) })
      .then(async (res) => {
        if (!res.ok && res.status !== 400) throw new Error(`http-${res.status}`);
        return (await res.json()) as FeedBody;
      })
      .then((body) => {
        if (!live) return;
        if (body.permissionDenied) {
          setState({
            phase: 'permission-denied',
            recommendations: body.recommendations ?? [],
            source: 'fallback',
          });
          return;
        }
        setState({
          phase: 'ready',
          recommendations: body.recommendations ?? [],
          source: body.source ?? 'fallback',
        });
      })
      .catch(() => {
        if (live) setState((prev) => ({ ...prev, phase: 'error' }));
      });

    return () => {
      live = false;
    };
  }, [subject, account?.id, account?.role, online, nonce]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  const actioned = useCallback<
    (id: string, decision: Decision, consequential?: boolean) => Promise<ActionResult>
  >(
    async (id, decision, consequential = false) => {
      try {
        const res = await fetch('/api/proactive', {
          method: 'POST',
          headers: { 'content-type': 'application/json', ...callerHeaders(account) },
          // The subject the feed was read against, so approve/execute resolve the
          // SAME engine recommendation (and the wall scopes ABAC on it).
          body: JSON.stringify({ id, decision, consequential, subject }),
        });
        if (res.status === 403) {
          // The wall denied / could not resolve the consequential op -> not committed.
          return { committed: false, denied: true, outcome: 'needs-approval' };
        }
        const data = (await res.json().catch(() => ({}))) as Partial<ActionResult>;
        return {
          committed: Boolean(data.committed),
          // The REAL execute outcome the route returned — never an echoed decision.
          outcome: typeof data.outcome === 'string' ? data.outcome : undefined,
          cleared: typeof data.cleared === 'boolean' ? data.cleared : undefined,
          stage: typeof data.stage === 'string' ? data.stage : undefined,
          source: data.source === 'gateway' || data.source === 'fallback' ? data.source : undefined,
        };
      } catch {
        // Network failure on the decision — stay safe (uncommitted), never throw.
        return { committed: false, outcome: 'needs-approval' };
      }
    },
    [account?.id, account?.role, subject],
  );

  return { ...state, refresh, actioned };
}
