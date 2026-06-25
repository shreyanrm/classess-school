import { test, expect, type Page } from '@playwright/test';
import { seedSession, openOrb, useTypedComposer, setComposerText } from './helpers';

/* ============================================================================
   vidya-paths.spec — the 5-path generative chat (spec 16.2), end to end.

   A request to Vidya takes EXACTLY ONE of five paths, and the thread shows a
   quiet, legible "what just happened" line (the `.vidya-path[data-path]` marker)
   so the taxonomy is honest:

     Path 1 — answer      : prose in the thread, no component manufactured.
     Path 2 — compose     : a live, verified component rendered IN-thread.
     Path 3 — act         : a consequential task is PREPARED behind the permission
                            ladder (an ApprovalControl), never auto-fired in chat.
     Path 4 — route+dock  : the task needs a workspace; Vidya routes there + docks.
     Path 5 — route+guide : Vidya routes there AND draws the on-screen steps.

   The orchestrator endpoint (/api/vidya/chat) is MOCKED per path so the turns
   are deterministic and provider-free (the same approach the base vidya.spec
   uses). The classifier is a pure projection of the returned actions, so the
   visible path marker is the reliable contract — and is what we assert, alongside
   the path-specific surface (inline card / approval ladder).

   The orb encumbers Playwright's trusted-input pipe, so the SPA navigation a
   Path-4/5 turn fires is not asserted by URL here (that client-route push is a
   known harness limitation — navigation.spec proves every route loads via real
   page loads); we assert the PATH the turn took, which is the spec's contract.
   ============================================================================ */

/** Send a typed turn into the orb and return once the user bubble is in-thread. */
async function ask(page: Page, prompt: string): Promise<void> {
  await openOrb(page);
  await useTypedComposer(page);
  const input = page.getByTestId('vidya-composer-input');
  await setComposerText(page, prompt);
  await input.dispatchEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true });
  await expect(page.getByTestId('vidya-panel')).toContainText(prompt);
}

/** Mock the orchestrator to return a fixed turn for the next ask. */
async function mockTurn(
  page: Page,
  body: { text: string; actions: unknown[] },
): Promise<void> {
  await page.route('**/api/vidya/chat', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
}

test.describe('Vidya — the 5 generative paths', () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page, 'teacher');
    await page.goto('/');
    await expect(page.getByTestId('role-landing')).toBeVisible();
  });

  test('Path 1 — answer: a question gets prose inline (no manufactured component)', async ({
    page,
  }) => {
    await mockTurn(page, { text: 'Class 10-B is on track; fractions is the one topic to watch.', actions: [] });
    await ask(page, 'how is my class doing?');

    const panel = page.getByTestId('vidya-panel');
    await expect(panel).toContainText('Class 10-B is on track');
    // A plain answer carries no path label (the answer path needs none) and no
    // inline card / surface.
    await expect(panel.locator('.vidya-path[data-path="compose"]')).toHaveCount(0);
    await expect(panel.locator('.vidya-path[data-path="act"]')).toHaveCount(0);
  });

  test('Path 2 — compose: ask-for-a-view renders a live component in-thread', async ({ page }) => {
    await mockTurn(page, {
      text: 'Here are the gaps I am seeing in equivalent fractions.',
      actions: [
        {
          type: 'render',
          spec: {
            kind: 'gaps',
            topic: 'Equivalent fractions',
            gaps: [
              { label: 'Finding a common denominator', rationale: 'Most attempts stall here.', confidence: 'high', confirmed: true },
            ],
          },
        },
      ],
    });
    await ask(page, 'show me the gaps in fractions');

    const panel = page.getByTestId('vidya-panel');
    // The compose path is named, and the live component (the gap content) is
    // rendered in-thread — not just prose.
    await expect(panel.locator('.vidya-path[data-path="compose"]')).toBeVisible();
    await expect(panel).toContainText(/finding a common denominator/i);
  });

  test('Path 3 — act: a consequential task is PREPARED behind the permission ladder', async ({
    page,
  }) => {
    await mockTurn(page, {
      text: 'I have drafted a short check for you to review.',
      actions: [
        {
          type: 'render',
          spec: {
            kind: 'draft',
            title: 'Quick check — equivalent fractions',
            topic: 'Equivalent fractions',
            body: 'Five quick items to confirm the reset landed.',
            items: ['Compare 1/2 and 2/4', 'Simplify 6/8'],
            confidence: 'high',
            requiresApproval: true,
            openHref: '/teacher/assign',
            openLabel: 'Review and set live',
          },
        },
      ],
    });
    await ask(page, 'make a quick check on fractions');

    const panel = page.getByTestId('vidya-panel');
    // The act path is named, and the draft is prepared with the review hand-off —
    // the ladder is NOT bypassed in chat: it waits for a human to set it live.
    await expect(panel.locator('.vidya-path[data-path="act"]')).toBeVisible();
    await expect(panel).toContainText(/quick check — equivalent fractions/i);
    await expect(panel).toContainText(/review and set live/i);
  });

  test('Path 4 — route+dock: a workspace task takes the route-dock path', async ({ page }) => {
    await mockTurn(page, {
      text: 'This needs the assignment workspace — opening it for you.',
      actions: [{ type: 'navigate', target: '/teacher/assign' }],
    });
    await ask(page, 'set up the fractions assignment');

    // The route-dock path is named (the SPA push itself is a known harness
    // limitation under the orb's input state; the taxonomy marker is the
    // contract and is set deterministically by the classifier).
    await expect(page.getByTestId('vidya-panel').locator('.vidya-path[data-path="route-dock"]')).toBeVisible();
  });

  test('Path 5 — route+guide: routing WITH an on-screen guide takes route-guide', async ({
    page,
  }) => {
    await mockTurn(page, {
      text: 'Let me take you there and point to the gaps.',
      actions: [
        { type: 'navigate', target: '/teacher/insights' },
        { type: 'highlight', region: 'gap-list', label: 'Start here' },
      ],
    });
    await ask(page, 'where are the biggest gaps, walk me through it');

    await expect(page.getByTestId('vidya-panel').locator('.vidya-path[data-path="route-guide"]')).toBeVisible();
  });
});
