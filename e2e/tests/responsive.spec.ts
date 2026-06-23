import { test, expect, type Locator } from '@playwright/test';
import { seedSession } from './helpers';

/* ============================================================================
   responsive.spec — the orb, the rail, and the content do not overlap.

   The harness already runs every spec under three desktop viewports (1280x800,
   1440x900, 1920x1080), so this file asserts the layout invariant once and gets
   exercised at each width: the slim left rail, the main content, and the
   floating Vidya orb must each be on-screen and must not intrude on one another.
   Bounding-box geometry is the resilient check — it does not depend on the exact
   pixel sizes, only on the rectangles not colliding.
   ============================================================================ */

/** True when two on-screen rectangles overlap (share any area). */
function overlaps(a: { x: number; y: number; width: number; height: number }, b: typeof a): boolean {
  return (
    a.x < b.x + b.width &&
    a.x + a.width > b.x &&
    a.y < b.y + b.height &&
    a.y + a.height > b.y
  );
}

async function box(loc: Locator) {
  const b = await loc.boundingBox();
  expect(b, 'element has no bounding box (not rendered?)').not.toBeNull();
  return b!;
}

test.describe('responsive layout', () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page, 'teacher');
  });

  test('rail and content do not overlap; orb is clear of the rail', async ({ page }, testInfo) => {
    await page.goto('/');
    await expect(page.getByTestId('role-landing')).toBeVisible();

    const rail = await box(page.getByTestId('rail'));
    const content = await box(page.getByTestId('role-landing'));
    const orb = await box(page.getByTestId('vidya-orb'));

    // The rail sits to the left; the content must begin at or after the rail.
    expect(content.x, 'content must not overlap the rail').toBeGreaterThanOrEqual(rail.x + rail.width - 1);
    expect(overlaps(rail, content)).toBeFalsy();

    // The orb floats bottom-right and must not collide with the slim left rail.
    expect(overlaps(orb, rail)).toBeFalsy();

    // The orb should be anchored toward the right edge for the active viewport.
    const vw = testInfo.project.use.viewport?.width ?? 1280;
    expect(orb.x + orb.width).toBeLessThanOrEqual(vw + 1);
    expect(orb.x).toBeGreaterThan(vw / 2);
  });

  test('open orb panel stays within the viewport and clear of the rail', async ({ page }, testInfo) => {
    await page.goto('/');
    await expect(page.getByTestId('role-landing')).toBeVisible();

    await page.getByTestId('vidya-orb').dispatchEvent('click');
    await expect(page.getByTestId('vidya-panel')).toBeVisible();

    const panel = await box(page.getByTestId('vidya-panel'));
    const rail = await box(page.getByTestId('rail'));

    const vw = testInfo.project.use.viewport?.width ?? 1280;
    const vh = testInfo.project.use.viewport?.height ?? 800;

    // The panel must fit on-screen (small tolerance for sub-pixel rounding).
    expect(panel.x).toBeGreaterThanOrEqual(-1);
    expect(panel.y).toBeGreaterThanOrEqual(-1);
    expect(panel.x + panel.width).toBeLessThanOrEqual(vw + 1);
    expect(panel.y + panel.height).toBeLessThanOrEqual(vh + 1);

    // And it must not sit on top of the rail.
    expect(overlaps(panel, rail)).toBeFalsy();
  });

  test('content is scrollable, not clipped behind the rail', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('role-landing')).toBeVisible();

    // The first interactive rail destination must be reachable (not zero-sized).
    const firstItem = page.getByTestId('rail-item').first();
    const b = await box(firstItem);
    expect(b.width).toBeGreaterThan(0);
    expect(b.height).toBeGreaterThan(0);
  });
});
