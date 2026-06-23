'use client';

/* ============================================================================
   lib/RoleContext.tsx — the role-shaped shell, one provider.

   The home and every destination page share a single Role so the rail's role
   switcher (Teacher <-> Student) persists as the user moves between pages. The
   role is held in the provider and mirrored to sessionStorage so a route change
   keeps the chosen role. One shell, role-shaped — never four apps.
   ============================================================================ */

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import type { Role } from './mock';
import { readStore, setAccountRole } from './store';

interface RoleContextValue {
  role: Role;
  setRole: (role: Role) => void;
  cycleRole: () => void;
}

const RoleContext = createContext<RoleContextValue | null>(null);

const STORAGE_KEY = 'clss.web.role';
const ORDER: Role[] = ['teacher', 'student', 'admin', 'parent'];

/**
 * Mirror the chosen role to sessionStorage (survives route changes in this tab)
 * AND into the localStorage account (survives a full restart). The account is the
 * durable home: a returning, authenticated user must land on THEIR role, not the
 * hard-coded default. Both writes are guarded — neither is fatal when storage is
 * unavailable (private mode / SSR).
 */
function persistRole(next: Role): void {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, next);
  } catch {
    // Non-fatal: the role still updates in memory for this session.
  }
  // Persist into the same localStorage store as the account so it survives a
  // restart; only writes when an account exists (setAccountRole is a no-op
  // otherwise), so it never resurrects a signed-out identity.
  try {
    setAccountRole(next);
  } catch {
    // Non-fatal.
  }
}

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>('teacher');

  // Hydrate the chosen role after mount (avoids SSR drift). Prefer the
  // sessionStorage value (the role chosen earlier in this tab); when absent —
  // e.g. after a full restart — seed it from the persisted account role so an
  // authenticated non-teacher lands on their own surface, not the default.
  useEffect(() => {
    try {
      const stored = window.sessionStorage.getItem(STORAGE_KEY) as Role | null;
      if (stored && ORDER.includes(stored)) {
        setRoleState(stored);
        return;
      }
    } catch {
      // sessionStorage may be unavailable (private mode); fall through to store.
    }
    const accountRole = readStore().account?.role;
    if (accountRole && ORDER.includes(accountRole)) {
      setRoleState(accountRole);
      // Seed sessionStorage so the rest of this tab's navigation is stable.
      try {
        window.sessionStorage.setItem(STORAGE_KEY, accountRole);
      } catch {
        // Non-fatal.
      }
    }
  }, []);

  const setRole = useCallback((next: Role) => {
    setRoleState(next);
    persistRole(next);
  }, []);

  const cycleRole = useCallback(() => {
    setRoleState((prev) => {
      const next = ORDER[(ORDER.indexOf(prev) + 1) % ORDER.length] ?? 'teacher';
      persistRole(next);
      return next;
    });
  }, []);

  return <RoleContext.Provider value={{ role, setRole, cycleRole }}>{children}</RoleContext.Provider>;
}

/**
 * Read the shared role. Falls back to a local teacher default when used outside
 * a provider (e.g. an isolated story), so a component is never crash-coupled to
 * the provider.
 */
export function useRole(): RoleContextValue {
  const ctx = useContext(RoleContext);
  if (ctx) return ctx;
  return {
    role: 'teacher',
    setRole: () => undefined,
    cycleRole: () => undefined,
  };
}
