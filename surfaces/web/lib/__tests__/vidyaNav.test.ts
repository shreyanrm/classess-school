import { describe, it, expect } from 'vitest';
import { readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { NAV_TARGETS, isNavTarget } from '../vidya';

/* ============================================================================
   Locks Vidya's navigation contract to the REAL routes.

   1) Every navigable page.tsx under app/ (excluding the auth + onboarding flows
      Vidya must never route into) is present in NAV_TARGETS — so plain-language
      navigation can reach every real destination.
   2) isNavTarget is the single guard; unknown targets are rejected.
   ============================================================================ */

const APP_DIR = resolve(__dirname, '../../app');

/** Routes Vidya must NOT navigate to (no signed-in shell there). */
const EXCLUDED = new Set(['/sign-in', '/sign-up', '/forgot-password', '/reset-password', '/welcome', '/welcome/personalise']);

/** Walk app/ and collect normalised routes from every page.tsx. */
function collectRoutes(dir: string, base = ''): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      // Route groups like (auth) do not contribute a path segment.
      const seg = entry.startsWith('(') && entry.endsWith(')') ? '' : `/${entry}`;
      out.push(...collectRoutes(full, base + seg));
    } else if (entry === 'page.tsx') {
      out.push(base === '' ? '/' : base);
    }
  }
  return out;
}

describe('Vidya navigation enum covers every real route', () => {
  const routes = collectRoutes(APP_DIR);

  it('finds the app routes (sanity)', () => {
    expect(routes.length).toBeGreaterThan(20);
    expect(routes).toContain('/');
    expect(routes).toContain('/teacher/attendance');
    expect(routes).toContain('/admin/setup');
  });

  it('includes every navigable (non-auth, non-onboarding) route in NAV_TARGETS', () => {
    const navigable = routes.filter((r) => !EXCLUDED.has(r));
    const missing = navigable.filter((r) => !isNavTarget(r));
    expect(missing).toEqual([]);
  });

  it('every NAV_TARGET is a real route (no dangling destinations)', () => {
    const realset = new Set(routes);
    const dangling = NAV_TARGETS.filter((t) => !realset.has(t));
    expect(dangling).toEqual([]);
  });

  it('rejects an unknown target', () => {
    expect(isNavTarget('/not-a-real-route')).toBe(false);
    expect(isNavTarget(42)).toBe(false);
  });
});
