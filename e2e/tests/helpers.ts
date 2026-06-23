import { expect, type Page } from '@playwright/test';

/* ============================================================================
   e2e/tests/helpers.ts — resilient, shared steps for the Classess harness.

   The web surface runs in demo mode by default (no Supabase configured): the
   session is a local Account persisted in localStorage under STORE_KEY. These
   helpers either complete the real stepped auth flow, or seed a demo session
   directly so a spec can land on a signed-in shell without re-walking auth in
   every test. Selectors prefer the stable data-testids already in the app.
   ============================================================================ */

/** The one localStorage key the web store writes (lib/store.ts STORE_KEY). */
export const STORE_KEY = 'clss.web.store.v1';

export type Role = 'student' | 'teacher' | 'admin' | 'parent';

/**
 * Seed a signed-in demo session directly into localStorage, so a spec that is
 * not testing auth can start on a signed-in shell. Mirrors the Account shape
 * lib/auth.localSignIn writes. Must be called before navigating to a page that
 * reads the store on mount (use page.addInitScript so it lands pre-hydration).
 */
export async function seedSession(page: Page, role: Role = 'teacher'): Promise<void> {
  await page.addInitScript(
    ([key, r]) => {
      const account = {
        id: `e2e-${r}-${Date.now()}`,
        role: r,
        method: 'phone-otp',
        contactHint: 'Demo account',
        demo: true,
        createdAt: new Date().toISOString(),
      };
      try {
        const raw = window.localStorage.getItem(key);
        const state = raw ? JSON.parse(raw) : {};
        state.account = account;
        window.localStorage.setItem(key, JSON.stringify(state));
      } catch {
        window.localStorage.setItem(key, JSON.stringify({ account }));
      }
    },
    [STORE_KEY, role] as const,
  );
}

/**
 * Complete the real stepped sign-in (email -> password) in demo mode, where any
 * email/password is accepted and lands on the role home. Returns once the role
 * landing is visible.
 */
export async function signInDemo(page: Page, role: Role = 'teacher'): Promise<void> {
  await seedSession(page, role); // ensure the post-redirect home has a session
  await page.goto('/sign-in');

  // Step 1: identifier (email).
  await expect(page.locator('[data-testid="auth-step"][data-step="identifier"]')).toBeVisible();
  await page.getByLabel('Email').fill('e2e@example.com');
  await page.getByTestId('auth-continue').click();

  // Step 2: secret (password).
  await expect(page.locator('[data-testid="auth-step"][data-step="secret"]')).toBeVisible();
  await page.getByLabel('Password', { exact: true }).fill('hunter2pw');
  await page.getByTestId('auth-continue').click();

  await expect(page.getByTestId('role-landing')).toBeVisible();
}

/** Open the Vidya orb panel and wait for it to appear. */
export async function openOrb(page: Page): Promise<void> {
  await page.getByTestId('vidya-orb').click();
  await expect(page.getByTestId('vidya-panel')).toBeVisible();
}

/**
 * Reveal the typed composer inside the orb. Voice is the primary mode, so the
 * composer is collapsed behind a "type instead" affordance until clicked.
 */
export async function useTypedComposer(page: Page): Promise<void> {
  const typeInstead = page.getByTestId('vidya-type-instead');
  if (await typeInstead.isVisible().catch(() => false)) {
    await typeInstead.click();
  }
  await expect(page.getByTestId('vidya-composer')).toBeVisible();
}
