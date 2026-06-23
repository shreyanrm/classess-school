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

interface RoleContextValue {
  role: Role;
  setRole: (role: Role) => void;
  cycleRole: () => void;
}

const RoleContext = createContext<RoleContextValue | null>(null);

const STORAGE_KEY = 'clss.web.role';
const ORDER: Role[] = ['teacher', 'student', 'admin', 'parent'];

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>('teacher');

  // Hydrate the chosen role from sessionStorage after mount (avoids SSR drift).
  useEffect(() => {
    try {
      const stored = window.sessionStorage.getItem(STORAGE_KEY) as Role | null;
      if (stored && ORDER.includes(stored)) setRoleState(stored);
    } catch {
      // sessionStorage may be unavailable (private mode); default role stands.
    }
  }, []);

  const setRole = useCallback((next: Role) => {
    setRoleState(next);
    try {
      window.sessionStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Non-fatal: the role still updates in memory for this session.
    }
  }, []);

  const cycleRole = useCallback(() => {
    setRoleState((prev) => {
      const next = ORDER[(ORDER.indexOf(prev) + 1) % ORDER.length] ?? 'teacher';
      try {
        window.sessionStorage.setItem(STORAGE_KEY, next);
      } catch {
        // Non-fatal.
      }
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
