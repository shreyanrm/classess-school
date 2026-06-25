import { test, expect } from '@playwright/test';
import { seedSession, type Role } from './helpers';

/* ============================================================================
   source-honesty.spec — the gateway-first, observable-source non-negotiable.

   Every governed deep-read MUST declare WHICH source answered: the live spine
   through the gateway, or the honest on-device degrade — never a silent mock.
   The SurfaceShell deep-read pages render the <SourceNote/> (one calm line); this
   spec asserts that observable is present on each governed deep-read page, per
   role, so the seam can never go silent.

   (The live loop and the approval queue carry their OWN source-honesty readouts —
   the loop computes every reading live through the engine and says so; the queue
   notes "the last-known feed" when on fallback — so they are verified by their
   own specs, not this one.)
   ============================================================================ */

/** The observable SourceNote — gateway-live OR the honest on-device degrade. */
const SOURCE_NOTE = /read live from the intelligence spine|on the last-known on-device read/i;

/** Governed deep-read pages that render the canonical SourceNote line on their
 *  default view, by role. Shared deep reads (/insights, /content, /classroom,
 *  /messages) appear for every role. (A few surfaces — e.g. the live loop, the
 *  approval queue, the curriculum graph, the control centre, the per-topic
 *  progress detail — declare their source through their OWN inline readout
 *  rather than this exact line; those are covered by their own specs and the
 *  clean-console gate, so they are intentionally not listed here.) */
const SHARED: string[] = ['/insights', '/content', '/classroom', '/messages'];
const PER_ROLE: Record<Role, string[]> = {
  teacher: ['/teacher/insights', '/teacher/students', '/teacher/evaluate', '/teacher/attendance', '/teacher/assign', '/teacher/growth'],
  student: ['/student/practice', '/student/mocks', '/student/portfolio', '/student/work'],
  admin: ['/admin/intelligence', '/admin/network', '/admin/governance', '/admin/exams'],
  parent: ['/parent/child', '/parent/reports', '/parent/together'],
};

const ROLES: Role[] = ['student', 'teacher', 'admin', 'parent'];

for (const role of ROLES) {
  test.describe(`source honesty — ${role}`, () => {
    const pages = Array.from(new Set([...SHARED, ...PER_ROLE[role]]));

    test('every governed deep-read declares its source (SourceNote present)', async ({ page }) => {
      test.setTimeout(120_000);
      await seedSession(page, role);

      for (const href of pages) {
        await page.goto(href, { waitUntil: 'domcontentloaded' });
        await expect(page.getByTestId('rail')).toBeVisible({ timeout: 15_000 });
        // The honest seam: the read either came live from the spine through the
        // gateway, or fell back to the on-device read — and it SAYS which.
        await expect(page.getByText(SOURCE_NOTE).first(), `${href} is missing its SourceNote`).toBeVisible({
          timeout: 12_000,
        });
      }
    });
  });
}
