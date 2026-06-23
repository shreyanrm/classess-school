import { test, expect } from '@playwright/test';
import { seedSession, type Role } from './helpers';

/* ============================================================================
   navigation.spec — every rail destination resolves; role landings render.

   For each role we seed a demo session, land on the home (role landing), then
   walk every rail-item by its data-rail-href and assert the destination renders
   without a 404 / error boundary. Rail hrefs are read from the live DOM, so the
   test follows whatever the role's rail exposes — no hard-coded route list to
   drift out of sync.
   ============================================================================ */

const ROLES: Role[] = ['student', 'teacher', 'admin', 'parent'];

for (const role of ROLES) {
  test.describe(`navigation — ${role}`, () => {
    test.beforeEach(async ({ page }) => {
      await seedSession(page, role);
    });

    test('role landing renders on home', async ({ page }) => {
      await page.goto('/');
      await expect(page.getByTestId('role-landing')).toBeVisible();
      await expect(page.getByTestId('rail')).toBeVisible();
      // At least one rail destination is present for the role.
      await expect(page.getByTestId('rail-item').first()).toBeVisible();
    });

    test('every rail-item resolves without a 404', async ({ page }) => {
      await page.goto('/');
      await expect(page.getByTestId('rail')).toBeVisible();

      // Collect the destinations from the live rail.
      const hrefs = await page.getByTestId('rail-item').evaluateAll((els) =>
        els
          .map((el) => el.getAttribute('data-rail-href'))
          .filter((h): h is string => !!h),
      );
      // De-dupe while preserving order (some roles repeat shared destinations).
      const unique = Array.from(new Set(hrefs));
      expect(unique.length).toBeGreaterThan(0);

      for (const href of unique) {
        const res = await page.goto(href);
        // The HTTP layer must not 404 (Next renders not-found as a 404 status).
        expect(res, `no response for ${href}`).not.toBeNull();
        expect(res!.status(), `unexpected status for ${href}`).toBeLessThan(400);

        // The not-found and error boundaries must not be on screen.
        await expect(
          page.getByText(/page not found|404|this page could not be found/i),
        ).toHaveCount(0);
        // The shell rail should persist on every in-app destination.
        await expect(page.getByTestId('rail')).toBeVisible();
      }
    });
  });
}
