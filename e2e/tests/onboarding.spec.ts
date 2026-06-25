import { test, expect } from '@playwright/test';

/* ============================================================================
   onboarding.spec — the §1 first-run flow, end to end.

   The readiness bar requires a personalised, implicitly-profiling onboarding
   that is consent / age-tier gated. This walks the WHOLE shape:

     welcome  ->  sign-up (role -> phone-OTP-shape identifier -> secret)
              ->  implicit-profiling (a few natural taps, no questionnaire)
              ->  consent + age-tier gate (DPDP children's-data)
              ->  the role home (role landing renders).

   These pages live on the orb-free auth/onboarding routes, so REAL clicks and
   REAL client navigation are used here (the floating orb — which the rest of the
   harness drives with dispatched events — is hidden on /welcome + /sign-up +
   /welcome/personalise, so the input path is unencumbered).

   Demo mode is assumed (no Supabase): any identifier + secret is accepted and the
   create-account path lands on /welcome/personalise. The spec asserts the FLOW
   and the GATES (the steps, the consent/age-tier choices, the SourceNote on the
   governed profiling read), not credentials — so it holds with or without a live
   provider.
   ============================================================================ */

const step = (s: 'role' | 'identifier' | 'secret') =>
  `[data-testid="auth-step"][data-step="${s}"]`;

test.describe('§1 onboarding — welcome to the role home', () => {
  test('welcome introduces Vidya and the shape, then Begin enters sign-up', async ({ page }) => {
    await page.goto('/welcome');

    // The calm preamble: a title, the three-beat shape of what follows, and the
    // two ways in (Begin -> create; or an existing-account link to sign in).
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByRole('list', { name: /what happens next/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /sign in/i })).toBeVisible();

    // Begin advances into the one modern auth flow (create account).
    await page.getByRole('button', { name: /begin/i }).click();
    await expect(page).toHaveURL(/\/sign-up$/);
    await expect(page.locator(step('role'))).toBeVisible();
  });

  test('full flow: role -> identifier -> secret -> personalise -> consent -> home', async ({
    page,
  }) => {
    // Sign-up walks role -> email/phone -> secret. (The phone-OTP path + the
    // email path are both offered; we drive the email path, which carries the
    // same stepped shape.)
    await page.goto('/sign-up');

    // Step 1 — role. Choosing a role auto-advances (no continue button).
    await expect(page.locator(step('role'))).toBeVisible();
    await page.getByRole('radio', { name: /student/i }).click();

    // Step 2 — identifier.
    await expect(page.locator(step('identifier'))).toBeVisible();
    await page.getByLabel('Email').fill('first.run@example.com');
    await page.getByTestId('auth-continue').click();

    // Step 3 — secret. The submit reads "Create account" on sign-up.
    await expect(page.locator(step('secret'))).toBeVisible();
    await expect(page.getByTestId('auth-continue')).toContainText(/create account/i);
    await page.getByLabel('Password', { exact: true }).fill('first-run-pw-9');
    await page.getByTestId('auth-continue').click();

    // The create-account path lands on the implicit-profiling finale.
    await expect(page).toHaveURL(/\/welcome\/personalise$/);

    // IMPLICIT PROFILING — a few natural taps, not a form. Vidya is docked and
    // narrates. The governed profiling read carries an observable SourceNote from
    // the first frame (no silent mock): the seam is honest here AND on the gate.
    await expect(page.getByText(/read live from the intelligence spine|on the last-known on-device read/i).first()).toBeVisible();

    // Make the natural choices: an intent (always present), and — for a student —
    // a subject. Each is a single tap (a SuggestionChip) that flips aria-pressed.
    // Continue is DISABLED until the required choices are made — proving the gate
    // is real, not cosmetic.
    const cont = page.getByRole('button', { name: /continue/i });
    await expect(cont).toBeDisabled();

    // The chip rows are, in order: language, intent, subject (student/parent),
    // goal. Pick an intent and a subject by their stable labels.
    const rows = page.locator('.auth-chip-row');
    await rows.nth(1).getByRole('button').first().click(); // an intent
    await rows.nth(2).getByRole('button').first().click(); // a subject

    // Now the gate opens. Continue advances to the CONSENT + AGE-TIER step.
    await expect(cont).toBeEnabled();
    await cont.click();

    // The consent gate: an age-tier choice (the lawful gate) + a clear, plain
    // explanation, and the SourceNote is still present (governed read).
    await expect(page.getByText(/your age, so i stay within the law/i)).toBeVisible();
    await expect(
      page.getByText(/read live from the intelligence spine|on the last-known on-device read/i).first(),
    ).toBeVisible();

    // The two consent outcomes are both offered (agree to personalise / not now)
    // — consent is a real, revocable decision, never assumed.
    await expect(page.getByRole('button', { name: /personalise for me|a guardian agrees/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /not now/i })).toBeVisible();

    // Decide: personalise for me (adult tier is the default). This persists the
    // tier-bounded profile and lands the role home.
    await page.getByRole('button', { name: /personalise for me/i }).click();

    // The finale completes onboarding and routes home (router.replace('/')),
    // where the role landing renders (the signed-in shell). The orb returns.
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByTestId('role-landing')).toBeVisible();
    await expect(page.getByTestId('rail')).toBeVisible();
  });

  test('the finale is skippable — skipping lands a calm, un-profiled home', async ({ page }) => {
    // A first-run user must never be trapped in profiling: Skip is always offered
    // and lands the role home without persisting a profile.
    await page.goto('/sign-up');
    await page.getByRole('radio', { name: /teacher/i }).click();
    await page.getByLabel('Email').fill('skip.run@example.com');
    await page.getByTestId('auth-continue').click();
    await page.getByLabel('Password', { exact: true }).fill('skip-run-pw-9');
    await page.getByTestId('auth-continue').click();

    await expect(page).toHaveURL(/\/welcome\/personalise$/);
    await page.getByRole('button', { name: /skip for now/i }).click();

    await expect(page.getByTestId('role-landing')).toBeVisible();
  });
});
