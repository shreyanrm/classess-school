'use client';

/* ============================================================================
   lib/adminConfig.ts — the CLIENT-SAFE seam + React hook for the six seed-only
   admin config surfaces (calendar, curriculum, exams, integrations,
   intelligence, network).

   The browser side of /api/admin-config. It carries NO secret and imports no
   database module — safe to bundle into a client component. Like lib/governance
   / lib/events it only PREPARES well-formed requests and POSTs them to the server
   route, which authorizes at the wall and appends to the immutable
   platform.events store. A faithful, keyed twin of useGovernance.

   GRACEFUL DEGRADATION: every call is best-effort and NEVER throws. When the
   wall denies, the db is unconfigured, or the network fails, the persist call
   resolves to { persisted:false } and the read hook degrades to the seed — the
   surface keeps working on its seed data, nothing crashes, nothing blanks.

   It exposes the five designed ReadStates (loading/error/offline/permission-
   denied/ready) for the config rehydrate so each surface ships them all from one
   place, the same way useGovernance / useProactive do.
   ============================================================================ */

import { useCallback, useEffect, useState } from 'react';
import { useStore } from './useStore';
import { useOnline } from './useOnline';
import type { ReadPhase } from './useDeepReads';

export const ADMIN_CONFIG_ROUTE = '/api/admin-config';

/** The surfaces this seam serves. The route bounds the same set server-side. */
export type AdminConfigSurface =
  | 'calendar'
  | 'curriculum'
  | 'exams'
  | 'integrations'
  | 'intelligence'
  | 'network'
  | 'operations'
  | 'control-centre';

/** A config value is a plain scalar the surface owns. */
export type AdminConfigValue = string | number | boolean;

/** key -> value, rehydrated from the immutable event store (last write wins). */
export type AdminConfigMap = Record<string, AdminConfigValue>;

/** The opaque caller headers the route needs to build the wall identity. */
function callerHeaders(account: { id?: string; role?: string } | null): Record<string, string> {
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  if (account?.id) headers['x-caller-uuid'] = account.id;
  if (account?.role) headers['x-caller-role'] = account.role;
  headers['x-caller-app'] = 'school';
  return headers;
}

/** The result of a config persist. `denied` is true on a wall refusal. */
export interface AdminConfigPersistResult {
  persisted: boolean;
  denied?: boolean;
}

interface ConfigGetBody {
  persisted: boolean;
  config?: AdminConfigMap;
}

export interface UseAdminConfig {
  /** The five designed states for the rehydrate read. */
  phase: ReadPhase;
  /** Whether the live config came from the event store ('gateway') or the seed
   *  ('fallback'). Surfaced so the page can quietly note the source. */
  source: 'gateway' | 'fallback';
  /** The persisted config (empty until the read resolves; merged over the seed). */
  config: AdminConfigMap;
  /** Re-run the rehydrate read (manual retry from the error state). */
  refresh: () => void;
  /** Persist one config set. Authorized at the wall, appended to the event store.
   *  Optimistically merges into the local map so the choice reads back at once. */
  set: (key: string, value: AdminConfigValue) => Promise<AdminConfigPersistResult>;
}

/**
 * Rehydrate one surface's config on mount (a real round-trip to the event store),
 * expose the persist call, and surface the five designed read states. Never
 * throws; degrades to the seed. A faithful, keyed twin of useGovernance.
 */
export function useAdminConfig(surface: AdminConfigSurface): UseAdminConfig {
  const { account } = useStore();
  const online = useOnline();
  const [phase, setPhase] = useState<ReadPhase>('loading');
  const [source, setSource] = useState<'gateway' | 'fallback'>('fallback');
  const [config, setConfig] = useState<AdminConfigMap>({});
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!online) {
      setPhase('offline');
      return;
    }
    if (!account?.id) {
      // No account yet -> nothing to rehydrate; the surface shows its seed baseline.
      setPhase('ready');
      setSource('fallback');
      return;
    }
    let live = true;
    setPhase('loading');

    fetch(
      `${ADMIN_CONFIG_ROUTE}?actor=${encodeURIComponent(account.id)}&surface=${encodeURIComponent(surface)}`,
      { headers: callerHeaders(account) },
    )
      .then(async (res) => {
        if (res.status === 403) {
          if (live) setPhase('permission-denied');
          return null;
        }
        if (!res.ok && res.status !== 400) throw new Error(`http-${res.status}`);
        return (await res.json()) as ConfigGetBody;
      })
      .then((body) => {
        if (!live || body === null) return;
        if (body.persisted) {
          setConfig(body.config ?? {});
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
  }, [account?.id, account?.role, online, surface, nonce]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  const set = useCallback<UseAdminConfig['set']>(
    async (key, value) => {
      // Optimistically reflect the choice so the surface reads it back at once,
      // even on the degraded (no-db) path — the seed-over-merge stays coherent.
      setConfig((prev) => ({ ...prev, [key]: value }));
      if (!account?.id) return { persisted: false };
      try {
        const res = await fetch(ADMIN_CONFIG_ROUTE, {
          method: 'POST',
          headers: callerHeaders(account),
          body: JSON.stringify({ surface, key, value }),
        });
        if (res.status === 403) return { persisted: false, denied: true };
        const data = (await res.json().catch(() => ({}))) as { persisted?: boolean };
        if (data.persisted) setSource('gateway');
        return { persisted: Boolean(data.persisted) };
      } catch {
        return { persisted: false };
      }
    },
    [account?.id, account?.role, surface],
  );

  return { phase, source, config, refresh, set };
}
