import { test, expect } from '@playwright/test';

/* ============================================================================
   auth.spec — the familiar, stepped auth surface.

   Verifies the stepped flow people already know: create-account advances
   role -> email -> password; sign-in advances email -> password. Back steps
   return to the previous view, and the social sign-in buttons are present on the
   first identifier view. Demo mode is assumed (no Supabase), so any email +
   password lands on the role home — but these tests assert flow + structure
   (the stable testids/steps), not credentials, so they hold either way.
   ============================================================================ */

const step = (s: 'role' | 'identifier' | 'secret') => `[data-testid="auth-step"][data-step="${s}"]`;

test.describe('stepped sign-up', () => {
  test('advances role -> email -> password', async ({ page }) => {
    await page.goto('/sign-up');

    // Step 1: role. Choosing a role advances automatically (no continue button).
    await expect(page.locator(step('role'))).toBeVisible();
    await expect(page.getByTestId('auth-continue')).toHaveCount(0);
    await page.getByRole('radio', { name: /student/i }).click();

    // Step 2: identifier (email).
    await expect(page.locator(step('identifier'))).toBeVisible();
    await expect(page.getByLabel('Email')).toBeVisible();
    await page.getByLabel('Email').fill('new.student@example.com');
    await page.getByTestId('auth-continue').click();

    // Step 3: secret (password). The submit reads "Create account" on sign-up.
    await expect(page.locator(step('secret'))).toBeVisible();
    await expect(page.getByLabel('Password', { exact: true })).toBeVisible();
    await expect(page.getByTestId('auth-continue')).toContainText(/create account/i);
  });

  test('Back returns to the previous step', async ({ page }) => {
    await page.goto('/sign-up');
    await page.getByRole('radio', { name: /teacher/i }).click();
    await expect(page.locator(step('identifier'))).toBeVisible();

    // From identifier, Back returns to role.
    await page.getByTestId('auth-back').click();
    await expect(page.locator(step('role'))).toBeVisible();

    // Forward again, then on to secret, then Back to identifier.
    await page.getByRole('radio', { name: /teacher/i }).click();
    await page.getByLabel('Email').fill('back.test@example.com');
    await page.getByTestId('auth-continue').click();
    await expect(page.locator(step('secret'))).toBeVisible();
    await page.getByTestId('auth-back').click();
    await expect(page.locator(step('identifier'))).toBeVisible();
  });
});

test.describe('stepped sign-in', () => {
  test('advances email -> password', async ({ page }) => {
    await page.goto('/sign-in');

    // Sign-in skips the role step: it opens directly on identifier.
    await expect(page.locator(step('identifier'))).toBeVisible();
    await expect(page.locator(step('role'))).toHaveCount(0);
    await page.getByLabel('Email').fill('returning@example.com');
    await page.getByTestId('auth-continue').click();

    await expect(page.locator(step('secret'))).toBeVisible();
    await expect(page.getByLabel('Password', { exact: true })).toBeVisible();
    await expect(page.getByTestId('auth-continue')).toContainText(/sign in/i);
  });

  test('Back returns from password to email', async ({ page }) => {
    await page.goto('/sign-in');
    await page.getByLabel('Email').fill('returning@example.com');
    await page.getByTestId('auth-continue').click();
    await expect(page.locator(step('secret'))).toBeVisible();

    await page.getByTestId('auth-back').click();
    await expect(page.locator(step('identifier'))).toBeVisible();
    // The email is preserved across the back step.
    await expect(page.getByLabel('Email')).toHaveValue('returning@example.com');
  });

  test('invalid email holds on the identifier step', async ({ page }) => {
    await page.goto('/sign-in');
    await page.getByLabel('Email').fill('not-an-email');
    await page.getByTestId('auth-continue').click();
    // Stays on identifier and surfaces a calm, specific error (target the message
    // itself — other role="alert" regions can coexist on the page).
    await expect(page.locator(step('identifier'))).toBeVisible();
    await expect(page.getByText('Enter a valid email address.')).toBeVisible();
  });
});

test.describe('social sign-in', () => {
  test('Google / Apple / Microsoft buttons are present on the identifier view', async ({ page }) => {
    await page.goto('/sign-in');
    await expect(page.locator(step('identifier'))).toBeVisible();

    await expect(page.getByTestId('auth-social-google')).toBeVisible();
    await expect(page.getByTestId('auth-social-apple')).toBeVisible();
    await expect(page.getByTestId('auth-social-microsoft')).toBeVisible();
  });

  test('social buttons are also offered on sign-up identifier view', async ({ page }) => {
    await page.goto('/sign-up');
    await page.getByRole('radio', { name: /admin/i }).click();
    await expect(page.locator(step('identifier'))).toBeVisible();

    await expect(page.getByTestId('auth-social-google')).toBeVisible();
    await expect(page.getByTestId('auth-social-apple')).toBeVisible();
    await expect(page.getByTestId('auth-social-microsoft')).toBeVisible();
  });
});
