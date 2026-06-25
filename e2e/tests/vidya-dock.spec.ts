import { test, expect } from '@playwright/test';
import { seedSession, openOrb, useTypedComposer, setComposerText } from './helpers';

/* ============================================================================
   vidya-dock.spec — Vidya everywhere: floats on the homes, DOCKS on deep pages,
   hides on the auth/onboarding flows (spec 16.4 / 17).

   The dock is NOT a second Vidya — it is the SAME presence (the same orb logic +
   thread + permission ladder) rendered in the docked treatment on a deep
   workspace. The contract is the `data-docked="true"` root on a deep page and a
   floating root on a role home. The single orb persists across navigation
   because it is mounted once in the root layout.

   This proves: the orb is PRESENT on every signed-in page, it DOCKS on deep
   pages and FLOATS on homes, it is HIDDEN on the orb-free flows, and the docked
   presence is still a usable Vidya (opens, takes a typed turn).
   ============================================================================ */

const ROLE_HOMES = ['/', '/student', '/teacher', '/admin', '/parent'];
const DEEP_PAGES = ['/loop', '/insights', '/proactive', '/content', '/classroom', '/messages', '/profile', '/settings'];

test.describe('Vidya is present everywhere (floats / docks)', () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page, 'teacher');
  });

  test('the orb floats on the role home (not docked)', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('role-landing')).toBeVisible();
    const orb = page.getByTestId('vidya-orb');
    await expect(orb).toBeVisible();
    // The Vidya root is NOT in the docked treatment on a home.
    await expect(page.locator('.vidya-orb-root')).not.toHaveAttribute('data-docked', 'true');
  });

  for (const href of DEEP_PAGES) {
    test(`the orb DOCKS on the deep page ${href}`, async ({ page }) => {
      await page.goto(href);
      await expect(page.getByTestId('rail')).toBeVisible();
      // Same single presence, in the docked treatment: the root carries
      // data-docked="true" and the orb is still present (one Vidya, not two).
      await expect(page.locator('.vidya-orb-root[data-docked="true"]')).toBeVisible();
      await expect(page.getByTestId('vidya-orb')).toHaveCount(1);
    });
  }

  test('the docked presence is still a usable Vidya (opens, takes a typed turn)', async ({
    page,
  }) => {
    // Mock the chat route so the assertion is deterministic and provider-free.
    await page.route('**/api/vidya/chat', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ text: 'Docked and ready to drive this page.', actions: [] }),
      });
    });

    await page.goto('/loop');
    await expect(page.locator('.vidya-orb-root[data-docked="true"]')).toBeVisible();

    await openOrb(page);
    await useTypedComposer(page);
    const input = page.getByTestId('vidya-composer-input');
    await setComposerText(page, 'what does this stage prove?');
    await input.dispatchEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true });

    await expect(page.getByTestId('vidya-panel')).toContainText('what does this stage prove?');
    await expect(page.getByTestId('vidya-panel')).toContainText('Docked and ready to drive this page.');
  });

});

test.describe('Vidya is hidden on the orb-free flows', () => {
  // These run signed-OUT: a seeded session would bounce /welcome straight home
  // (OnboardingFlow sends an already-signed-in visitor to '/'), where the orb is
  // present — so we deliberately do NOT seed a session here.
  test('the orb does not appear on welcome / sign-in / sign-up (no shell to drive)', async ({
    page,
  }) => {
    await page.goto('/sign-in');
    await expect(page.locator('[data-testid="auth-step"]').first()).toBeVisible();
    await expect(page.getByTestId('vidya-orb')).toHaveCount(0);

    await page.goto('/sign-up');
    await expect(page.getByTestId('auth-step')).toBeVisible();
    await expect(page.getByTestId('vidya-orb')).toHaveCount(0);

    await page.goto('/welcome');
    await expect(page.getByRole('button', { name: /begin/i })).toBeVisible();
    await expect(page.getByTestId('vidya-orb')).toHaveCount(0);
  });
});
