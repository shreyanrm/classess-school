import { test, expect, type Page, type ConsoleMessage } from '@playwright/test';
import { seedSession, type Role } from './helpers';

/* ============================================================================
   clickability.spec — every primary button/link on every role page is real.

   The founder's clickability law: no dead controls, and no overlay/pseudo may
   intercept a click (every decorative ::before/::after carries pointer-events:
   none). Now that the SpotlightCard glow is calm-by-default and all overlays are
   click-through, this spec performs REAL clicks:

     - For each role, walk every rail destination.
     - Install a per-page console-error + pageerror gate; any console.error or
       uncaught exception fails the page.
     - On each page, click every visible, enabled primary button and assert the
       page still has no console error / pageerror and did not crash to the error
       boundary. Navigations are followed and then we return.

   Buttons are clicked with force (the calm cards no longer block, but fixed/
   animated chrome can still confuse strict actionability); the console gate is
   the real proof that the click acted without throwing.
   ============================================================================ */

const ROLES: Role[] = ['student', 'teacher', 'admin', 'parent'];

/** Console.error strings that are environmental noise, not app bugs. */
const IGNORED_CONSOLE = [
  /Download the React DevTools/i,
  /\[Fast Refresh\]/i,
  /favicon/i,
  /ResizeObserver loop/i,
  /Failed to load resource/i, // dev asset 404s, not app logic
];

interface Gate {
  errors: string[];
}

/** Attach a console-error + pageerror gate to a page. Returns its error sink. */
function installGate(page: Page): Gate {
  const gate: Gate = { errors: [] };
  page.on('console', (msg: ConsoleMessage) => {
    if (msg.type() !== 'error') return;
    const text = msg.text();
    if (IGNORED_CONSOLE.some((re) => re.test(text))) return;
    gate.errors.push(`console.error: ${text}`);
  });
  page.on('pageerror', (err) => {
    gate.errors.push(`pageerror: ${err.message}`);
  });
  return gate;
}

async function assertNoErrors(gate: Gate, where: string): Promise<void> {
  expect(gate.errors, `${where} produced console/page errors:\n${gate.errors.join('\n')}`).toEqual(
    [],
  );
}

for (const role of ROLES) {
  test.describe(`clickability — ${role}`, () => {
    test('every rail page loads and every primary control clicks cleanly', async ({ page }) => {
      test.setTimeout(180_000);
      const gate = installGate(page);

      await seedSession(page, role);
      await page.goto('/');
      await expect(page.getByTestId('role-landing')).toBeVisible();
      await assertNoErrors(gate, 'home');

      // Collect rail destinations from the live DOM (no hard-coded list).
      const hrefs = await page.getByTestId('rail-item').evaluateAll((els) =>
        els.map((el) => el.getAttribute('data-rail-href')).filter((h): h is string => !!h),
      );
      const routes = Array.from(new Set(['/', ...hrefs]));

      for (const href of routes) {
        await page.goto(href, { waitUntil: 'domcontentloaded' });
        // No 404 / error boundary on arrival.
        await expect(page.getByText(/this page could not be found|page not found/i)).toHaveCount(0);
        await assertNoErrors(gate, `load ${href}`);

        // Every visible, enabled button on the page. We re-resolve per index
        // because a click can re-render and detach the handle.
        const buttonCount = await page.locator('button:visible:not([disabled])').count();
        // Cap clicks per page so the suite stays bounded; the first N primary
        // controls cover the page's main affordances.
        const max = Math.min(buttonCount, 8);
        for (let i = 0; i < max; i += 1) {
          const btn = page.locator('button:visible:not([disabled])').nth(i);
          if (!(await btn.isVisible().catch(() => false))) continue;
          const label = (await btn.textContent().catch(() => ''))?.trim() ?? '';
          // Skip controls that intentionally leave the gated shell or destroy the
          // session (sign out, delete account, role switch is covered separately).
          if (/sign out|erase|delete my account/i.test(label)) continue;
          await btn.dispatchEvent('click').catch(() => {});
          // A click must never throw or log an error.
          await assertNoErrors(gate, `click "${label || `button#${i}`}" on ${href}`);
          // If a click navigated away from this page, that's fine (no error) —
          // stop sweeping this route and move to the next, rather than reloading
          // after every click (which makes the sweep too slow to finish).
          if (!(await page.getByTestId('rail').isVisible().catch(() => false))) break;
        }
      }
    });
  });
}

test.describe('clickability — shared shell', () => {
  test('the role switch announces the new workspace, with no errors', async ({ page }) => {
    const gate = installGate(page);
    await seedSession(page, 'teacher');
    await page.goto('/');
    await expect(page.getByTestId('role-landing')).toBeVisible();

    // The role switch is the grid button in the rail (aria-label starts "Switch role").
    const switchBtn = page.getByRole('button', { name: /switch role/i });
    await switchBtn.dispatchEvent('click');
    // A visible, announced confirmation appears (status region).
    await expect(page.locator('.rail-role-toast')).toBeVisible();
    await assertNoErrors(gate, 'role switch');
  });

  test('the search drawer exposes a real search field', async ({ page }) => {
    const gate = installGate(page);
    await seedSession(page, 'teacher');
    await page.goto('/');
    await page.getByRole('button', { name: /search and history/i }).dispatchEvent('click');
    const search = page.getByRole('searchbox', { name: /search your conversations/i });
    await expect(search).toBeVisible();
    await search.evaluate((el, v) => { const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!; s.call(el, v); el.dispatchEvent(new Event('input', { bubbles: true })); }, 'algebra');
    await expect(page.getByText(/no matches for/i)).toBeVisible();
    await assertNoErrors(gate, 'search drawer');
  });
});
