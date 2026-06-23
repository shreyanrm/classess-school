'use client';

/* ============================================================================
   lib/useStore.ts — the React binding for lib/store.ts.

   SSR-safe by construction: it uses useSyncExternalStore with a server snapshot
   of the empty state, so the server render and the first client render agree
   (no hydration drift), then the real persisted state is read after mount.

   Keep this the ONLY React-aware part of the persistence layer; lib/store.ts
   stays a pure, node-testable module.
   ============================================================================ */

import { useCallback, useSyncExternalStore } from 'react';
import {
  emptyState,
  readStore,
  subscribe,
  isFirstRun,
  type StoreState,
} from './store';

/** The empty server snapshot — identical on server and first client paint. */
const SERVER_SNAPSHOT: StoreState = emptyState();

/**
 * Read the persisted store and re-render on any write. Returns the current
 * state plus a couple of derived conveniences. On the server (and the first
 * client paint) it returns the empty state, so first-run routing must run in an
 * effect on the client — never during render.
 */
export function useStore() {
  const state = useSyncExternalStore(
    subscribe,
    readStore,
    useCallback(() => SERVER_SNAPSHOT, []),
  );

  return {
    state,
    account: state.account,
    onboarding: state.onboarding,
    consent: state.consent,
    profile: state.profile,
    school: state.school,
    preferences: state.preferences,
    firstRun: isFirstRun(state),
  };
}
