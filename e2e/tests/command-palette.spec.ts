import { test, expect, type Page } from '@playwright/test';
import { seedSession } from './helpers';

/* ============================================================================
   command-palette.spec — the universal Cmd/Ctrl-K launcher (spec 17.3-17.4).

   The keyboard twin of the orb, mounted once at the app root and available on
   EVERY surface. Cmd/Ctrl-K toggles a frosted palette; it filters the validated
   route set + "Ask Vidya"/"Talk to Vidya" entry points, and Cmd/Ctrl-/ opens the
   shortcut cheatsheet.

   The orb is mounted on these pages, which encumbers Playwright's trusted-input
   pipe — so, exactly as the rest of the harness does, this spec opens the palette
   with a DISPATCHED keydown and drives options with dispatched clicks. The
   "Ask Vidya" option's hand-off to the orb (a window event, immune to the input
   pipe) is asserted directly; the navigation "Go to" rows are asserted present +
   filterable (their full client-route push is covered by navigation.spec via
   real page loads).
   ============================================================================ */

/** Open the palette with a dispatched Cmd/Ctrl-K (the documented shortcut). */
async function openPalette(page: Page): Promise<void> {
  await page.evaluate(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
  });
  await expect(page.getByTestId('command-palette')).toBeVisible();
}

/** Type into the palette search with a native-setter fill (input-pipe safe). */
async function typePalette(page: Page, text: string): Promise<void> {
  await page.getByTestId('command-palette-input').evaluate((el, v) => {
    const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!;
    set.call(el, v);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }, text);
}

test.describe('command palette — the Cmd/Ctrl-K launcher', () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page, 'teacher');
    await page.goto('/');
    await expect(page.getByTestId('role-landing')).toBeVisible();
  });

  test('Cmd/Ctrl-K opens the palette with the suggested + go-to commands', async ({ page }) => {
    await openPalette(page);

    // The search field is focused and the command set is present: the two
    // suggested Vidya entry points, plus the "Go to" route rows.
    await expect(page.getByTestId('command-palette-input')).toBeVisible();
    await expect(page.locator('.cmdk-opt').filter({ hasText: /talk to vidya/i })).toBeVisible();
    await expect(page.locator('.cmdk-opt').filter({ hasText: /ask vidya/i })).toBeVisible();
    // At least one route destination is offered (the validated NAV set).
    await expect(page.locator('.cmdk-opt').filter({ hasText: /go to|\/loop|\/messages|\/proactive/i }).first()).toBeVisible();
  });

  test('typing filters the route set and the Ask row always survives', async ({ page }) => {
    await openPalette(page);
    await typePalette(page, 'loop');

    // The "Ask Vidya: …" row carries the typed query and always survives the
    // filter; the matching route ("/loop") is offered alongside it.
    await expect(page.locator('.cmdk-opt').filter({ hasText: /ask vidya: .loop/i })).toBeVisible();
    await expect(page.locator('.cmdk-opt').filter({ hasText: '/loop' })).toBeVisible();

    // A query that matches no route still keeps the Ask row (never a dead end).
    await typePalette(page, 'zxqwv-nonsense');
    await expect(page.locator('.cmdk-opt').filter({ hasText: /ask vidya/i })).toBeVisible();
  });

  test('"Ask Vidya" hands the typed query to the orb (opens the panel)', async ({ page }) => {
    await openPalette(page);
    await typePalette(page, 'how is my class doing');

    // Selecting the Ask row routes into the orb conversation: the palette closes
    // and the orb panel opens (openVidya is a window event, not a click-nav, so
    // it lands reliably). This is the keyboard twin reaching the orb.
    await page.locator('.cmdk-opt').filter({ hasText: /ask vidya/i }).first().dispatchEvent('click');
    await expect(page.getByTestId('command-palette')).toHaveCount(0);
    await expect(page.getByTestId('vidya-panel')).toBeVisible();
  });

  test('Cmd/Ctrl-/ opens the keyboard shortcut cheatsheet', async ({ page }) => {
    await page.evaluate(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: '/', metaKey: true, bubbles: true }));
    });
    const sheet = page.getByRole('dialog', { name: /keyboard shortcuts/i });
    await expect(sheet).toBeVisible();
    // The documented universal shortcuts are listed (never hidden).
    await expect(sheet.getByText(/open the command palette/i)).toBeVisible();
    await expect(sheet.getByText(/talk to vidya/i)).toBeVisible();
  });

  test('the palette is available on a deep page too (every surface)', async ({ page }) => {
    // Navigate to a deep workspace and confirm the launcher still answers — the
    // palette is mounted at the root, so it is universal.
    await page.goto('/proactive');
    await expect(page.getByTestId('rail')).toBeVisible();
    await openPalette(page);
    await expect(page.getByTestId('command-palette-input')).toBeVisible();
  });
});
