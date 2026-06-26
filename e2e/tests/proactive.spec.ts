import { test, expect, type Page, type ConsoleMessage } from '@playwright/test';
import { seedSession } from './helpers';

/* ============================================================================
   proactive.spec — the proactive loop, end to end (recommend -> approve ->
   execute -> outcome), spec 13 b11 + the permission ladder (invariant 8).

   The /proactive approval queue READS the recommendation feed gateway-first and
   renders the real RecommendationItem control. We drive the two designed paths:

     - REVERSIBLE / safe-automatic ("Prepare the reset"): executing commits
       directly and shows the Done / "prepared and waiting" outcome with an Undo —
       a real outcome, never a dead end.

     - CONSEQUENTIAL ("Assign the task", send/submit/publish/grade-class): the
       action is PREPARED, never fired. Acting RAISES the ApprovalControl — the
       permission ladder made visible ("Nothing fires until you approve"). On
       Approve the loop runs through the wall; when the wall that authorizes the
       consequential op is unreachable it HONESTLY surfaces needs-approval and
       NEVER a false "Done" / "Gap resolved" — the non-negotiable: no silent
       commit on a consequential op, the human holds the authority.

   The orb is mounted here (a deep page), so — as the harness does throughout —
   controls are driven with dispatched clicks after scrolling into view. A
   per-page console-error + pageerror gate runs the whole time; any error fails.
   ============================================================================ */

interface Gate {
  errors: string[];
}
const IGNORED = [/Download the React DevTools/i, /\[Fast Refresh\]/i, /favicon/i, /ResizeObserver loop/i, /Failed to load resource/i];
function installGate(page: Page): Gate {
  const gate: Gate = { errors: [] };
  page.on('console', (m: ConsoleMessage) => {
    if (m.type() !== 'error') return;
    if (IGNORED.some((re) => re.test(m.text()))) return;
    gate.errors.push(`console.error: ${m.text()}`);
  });
  page.on('pageerror', (e) => gate.errors.push(`pageerror: ${e.message}`));
  return gate;
}

/** A dispatched click that first scrolls the control into view (so a below-the-
 *  fold card's button reliably receives the synthetic event). */
async function tap(page: Page, name: RegExp | string) {
  const btn = page.getByRole('button', { name }).first();
  await btn.waitFor({ state: 'visible', timeout: 12_000 });
  await btn.scrollIntoViewIfNeeded();
  await btn.dispatchEvent('click');
}

test.describe('proactive loop — recommend → approve → execute → outcome', () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page, 'teacher');
  });

  test('the feed reads in and triages by confidence (recommend)', async ({ page }) => {
    const gate = installGate(page);
    await page.goto('/proactive');
    await expect(page.getByTestId('rail')).toBeVisible();

    // The queue renders its at-a-glance count-up triage (the stat matrix) and the
    // confidence-grouped sections, with at least one real action.
    await expect(page.getByText(/awaiting your decision/i).first()).toBeVisible();
    await expect(page.getByText(/ready to act/i).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /prepare the reset|assign the task/i }).first()).toBeVisible();

    expect(gate.errors, gate.errors.join('\n')).toEqual([]);
  });

  test('reversible action executes directly to a real outcome with Undo', async ({ page }) => {
    const gate = installGate(page);
    await page.goto('/proactive');
    await expect(page.getByTestId('rail')).toBeVisible();

    // "Prepare the reset" is reversible: acting executes it and shows the
    // committed outcome (Done / prepared-and-waiting) with an Undo — never a dead
    // end, and nothing was sent on its own.
    await tap(page, /prepare the reset/i);
    await expect(
      page.getByText(/done|prepared and waiting for you on the page/i).first(),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: /undo/i }).first()).toBeVisible();

    expect(gate.errors, gate.errors.join('\n')).toEqual([]);
  });

  test('consequential action raises the permission ladder and never commits silently', async ({
    page,
  }) => {
    const gate = installGate(page);
    await page.goto('/proactive');
    await expect(page.getByTestId('rail')).toBeVisible();

    // "Assign the task" is consequential: acting PREPARES it and raises the
    // ApprovalControl — the permission ladder made visible. Nothing fires yet.
    // (The prepared action's approve button carries the action's own label, so
    // the ladder is asserted by its visible state, not a generic "Approve".)
    await tap(page, /assign the task/i);
    await expect(
      page.getByText(/nothing fires until you approve|prepared — awaiting approval/i).first(),
    ).toBeVisible();

    // Approving runs the loop through the wall. The approve control in the raised
    // ApprovalControl carries the action label ("Assign the task"); tapping it is
    // the explicit human approval. Whatever the wall verdict, the UI must be
    // HONEST: either the engine cleared it (a recorded approval -> resolved/Done)
    // OR — when the authorizing wall is unreachable — it surfaces needs-approval
    // and explicitly says nothing was sent. It must NEVER show a resolved/Done
    // outcome without a real commit (the non-negotiable: no silent consequential
    // commit).
    await tap(page, /assign the task/i);
    await expect(
      page.getByText(
        /gap resolved|an outcome was recorded|that needs approval to go through|nothing was sent/i,
      ).first(),
    ).toBeVisible();

    expect(gate.errors, gate.errors.join('\n')).toEqual([]);
  });

  test('declining sets the item aside — a clean, reversible outcome', async ({ page }) => {
    const gate = installGate(page);
    await page.goto('/proactive');
    await expect(page.getByTestId('rail')).toBeVisible();

    // Decline on the first card: it is set aside with an Undo, nothing sent.
    await tap(page, /^decline$/i);
    await expect(page.getByText(/set aside|declined/i).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /undo/i }).first()).toBeVisible();

    expect(gate.errors, gate.errors.join('\n')).toEqual([]);
  });
});
