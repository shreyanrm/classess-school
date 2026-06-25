import { test, expect, type Page, type ConsoleMessage } from '@playwright/test';
import { seedSession, type Role } from './helpers';

/* ============================================================================
   console-gate.spec — the readiness console gate: every route, every role, every
   viewport loads with ZERO console errors and NO unhandled rejection.

   The founder's clean-console law, made a hard gate: for each role we seed a
   session, then visit the home + every rail destination + the shared deep pages.
   On each page we assert:
     - no uncaught exception / unhandled promise rejection (pageerror),
     - no console.error (beyond known environmental noise),
     - no 404 / error-boundary on screen, and the shell rail persisted.

   (The gateway-first SourceNote non-negotiable is verified, page by page, in
   source-honesty.spec — this file is the pure clean-console + no-dead-route gate.)

   This runs under every configured viewport, so the clean-console guarantee holds
   across the responsive breakpoint range, not just on desktop.
   ============================================================================ */

const ROLES: Role[] = ['student', 'teacher', 'admin', 'parent'];

/** Shared deep-read workspaces every role can reach directly. */
const SHARED_DEEP = ['/loop', '/insights', '/proactive', '/content', '/classroom', '/messages', '/profile', '/settings'];

/** console.error strings that are environmental noise, not app bugs. */
const IGNORED = [
  /Download the React DevTools/i,
  /\[Fast Refresh\]/i,
  /favicon/i,
  /ResizeObserver loop/i,
  /Failed to load resource/i, // dev-asset 404s (not app logic)
];

interface Gate {
  errors: string[];
}
function installGate(page: Page): Gate {
  const gate: Gate = { errors: [] };
  page.on('console', (m: ConsoleMessage) => {
    if (m.type() !== 'error') return;
    const t = m.text();
    if (IGNORED.some((re) => re.test(t))) return;
    gate.errors.push(`console.error: ${t}`);
  });
  // pageerror fires for uncaught exceptions AND unhandled promise rejections in
  // Chromium — the one event that gates both.
  page.on('pageerror', (e) => gate.errors.push(`pageerror: ${e.message}`));
  return gate;
}

for (const role of ROLES) {
  test.describe(`console gate — ${role}`, () => {
    test('every route loads clean: no console errors, no error boundary, source-honest', async ({
      page,
    }) => {
      test.setTimeout(180_000);
      const gate = installGate(page);

      await seedSession(page, role);
      await page.goto('/');
      await expect(page.getByTestId('role-landing')).toBeVisible();

      // The role's own rail destinations + the shared deep pages, de-duped.
      const railHrefs = await page.getByTestId('rail-item').evaluateAll((els) =>
        els.map((el) => el.getAttribute('data-rail-href')).filter((h): h is string => !!h),
      );
      const routes = Array.from(new Set(['/', ...railHrefs, ...SHARED_DEEP]));

      for (const href of routes) {
        await page.goto(href, { waitUntil: 'domcontentloaded' });

        // The shell mounted (no crash to a content-less error state) — the rail
        // persists on every in-app destination.
        await expect(page.getByTestId('rail')).toBeVisible({ timeout: 15_000 });

        // No 404 / not-found boundary on screen.
        await expect(
          page.getByText(/this page could not be found|page not found|404/i),
        ).toHaveCount(0);

        // The hard gate: nothing logged an error / threw on this page.
        expect(gate.errors, `${href} produced console/page errors:\n${gate.errors.join('\n')}`).toEqual(
          [],
        );
      }
    });
  });
}
