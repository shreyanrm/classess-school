'use client';

/* ============================================================================
   lib/governance.ts — the CLIENT-SAFE seam + React hook for the admin
   governance surface (GAP#3/#4/#5/#7).

   The browser side of /api/governance. It carries NO secret and imports no
   database module — it is safe to bundle into a client component. Like
   lib/events.ts / lib/opData.ts it only PREPARES well-formed requests and POSTs
   them to the server route, which authorizes at the wall and appends to the
   immutable platform.events store.

   GRACEFUL DEGRADATION: every call is best-effort and NEVER throws. When the
   wall denies, the db is unconfigured, or the network fails, the persist call
   resolves to { persisted:false } and the read hook degrades to the seed mock —
   the surface keeps working on its local store, nothing crashes, nothing blanks.

   It exposes the five designed ReadStates (loading/error/offline/permission-
   denied/ready) for the governance rehydrate so the surface ships them all from
   one place, the same way useProactive / useDeepReads do.
   ============================================================================ */

import { useCallback, useEffect, useState } from 'react';
import { useStore } from './useStore';
import { useOnline } from './useOnline';
import type { ReadPhase } from './useDeepReads';

export const GOVERNANCE_ROUTE = '/api/governance';

/** A persisted governance config rehydrated from the immutable event store. */
export interface GovernanceConfig {
  /** control id -> on (the last toggle wins). */
  aiControls: Record<string, boolean>;
  /** policy id -> version label in force. */
  policyVersions: Record<string, string>;
}

/** A governance audit entry, read back from platform.events (immutable). */
export interface GovernanceAuditEntry {
  id: string;
  when: string;
  action: string;
}

/** The opaque caller headers the route needs to build the wall identity. */
function callerHeaders(account: { id?: string; role?: string } | null): Record<string, string> {
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  if (account?.id) headers['x-caller-uuid'] = account.id;
  if (account?.role) headers['x-caller-role'] = account.role;
  headers['x-caller-app'] = 'school';
  return headers;
}

/** The result of a governance persist. `denied` is true on a wall refusal. */
export interface GovernancePersistResult {
  persisted: boolean;
  denied?: boolean;
}

/** POST one consequential governance action. Never throws. */
async function persist(
  account: { id?: string; role?: string } | null,
  body: Record<string, unknown>,
): Promise<GovernancePersistResult> {
  if (!account?.id) return { persisted: false };
  try {
    const res = await fetch(GOVERNANCE_ROUTE, {
      method: 'POST',
      headers: callerHeaders(account),
      body: JSON.stringify(body),
    });
    if (res.status === 403) return { persisted: false, denied: true };
    const data = (await res.json().catch(() => ({}))) as { persisted?: boolean };
    return { persisted: Boolean(data.persisted) };
  } catch {
    return { persisted: false };
  }
}

interface GovGetBody {
  persisted: boolean;
  config?: GovernanceConfig;
  audit?: GovernanceAuditEntry[];
}

export interface UseGovernance {
  /** The five designed states for the rehydrate read. */
  phase: ReadPhase;
  /** Whether the live config/audit came from the event store ('gateway') or the
   *  seed mock ('fallback'). Surfaced so the page can quietly note the source. */
  source: 'gateway' | 'fallback';
  /** The persisted config (empty until the read resolves; merged over defaults by the page). */
  config: GovernanceConfig;
  /** The immutable audit trail, newest-first (empty on the degraded path). */
  audit: GovernanceAuditEntry[];
  /** Re-run the rehydrate read (manual retry from the error state). */
  refresh: () => void;
  /** Persist an AI-control toggle. Authorized at the wall, appended to audit. */
  setAiControl: (controlId: string, controlLabel: string, on: boolean) => Promise<GovernancePersistResult>;
  /** Persist a policy version set in force. */
  setPolicy: (policyId: string, policyName: string, version: string) => Promise<GovernancePersistResult>;
  /** Record break-glass engagement (emits an event AND hits this audit endpoint). */
  recordBreakGlass: () => Promise<GovernancePersistResult>;
  /** Record an emergency disable (emits an event AND hits this audit endpoint). */
  recordEmergencyDisable: () => Promise<GovernancePersistResult>;
}

/**
 * Rehydrate governance config + the immutable audit trail on mount (a real
 * round-trip to the event store), expose the persist calls, and surface the
 * five designed read states. Never throws; degrades to the seed mock.
 */
export function useGovernance(): UseGovernance {
  const { account } = useStore();
  const online = useOnline();
  const [phase, setPhase] = useState<ReadPhase>('loading');
  const [source, setSource] = useState<'gateway' | 'fallback'>('fallback');
  const [config, setConfig] = useState<GovernanceConfig>({ aiControls: {}, policyVersions: {} });
  const [audit, setAudit] = useState<GovernanceAuditEntry[]>([]);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!online) {
      setPhase('offline');
      return;
    }
    if (!account?.id) {
      // No account yet -> nothing to rehydrate; the surface shows its baseline.
      setPhase('ready');
      setSource('fallback');
      return;
    }
    let live = true;
    setPhase('loading');

    fetch(`${GOVERNANCE_ROUTE}?actor=${encodeURIComponent(account.id)}`, {
      headers: callerHeaders(account),
    })
      .then(async (res) => {
        if (res.status === 403) {
          if (live) setPhase('permission-denied');
          return null;
        }
        if (!res.ok && res.status !== 400) throw new Error(`http-${res.status}`);
        return (await res.json()) as GovGetBody;
      })
      .then((body) => {
        if (!live || body === null) return;
        if (body.persisted) {
          setConfig(body.config ?? { aiControls: {}, policyVersions: {} });
          setAudit(body.audit ?? []);
          setSource('gateway');
        } else {
          setSource('fallback');
        }
        setPhase('ready');
      })
      .catch(() => {
        if (live) setPhase('error');
      });

    return () => {
      live = false;
    };
  }, [account?.id, account?.role, online, nonce]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  const setAiControl = useCallback<UseGovernance['setAiControl']>(
    (controlId, controlLabel, on) => persist(account, { kind: 'ai_control', controlId, controlLabel, on }),
    [account?.id, account?.role],
  );
  const setPolicy = useCallback<UseGovernance['setPolicy']>(
    (policyId, policyName, version) => persist(account, { kind: 'policy', policyId, policyName, version }),
    [account?.id, account?.role],
  );
  const recordBreakGlass = useCallback<UseGovernance['recordBreakGlass']>(
    () => persist(account, { kind: 'break_glass' }),
    [account?.id, account?.role],
  );
  const recordEmergencyDisable = useCallback<UseGovernance['recordEmergencyDisable']>(
    () => persist(account, { kind: 'emergency_disable' }),
    [account?.id, account?.role],
  );

  return {
    phase,
    source,
    config,
    audit,
    refresh,
    setAiControl,
    setPolicy,
    recordBreakGlass,
    recordEmergencyDisable,
  };
}
