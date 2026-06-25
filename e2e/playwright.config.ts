import { defineConfig, devices } from '@playwright/test';

/* ============================================================================
   e2e/playwright.config.ts — the Classess School end-to-end harness.

   Drives the Next.js web surface (surfaces/web) over its dev port. Desktop-only
   viewports for now (the product is a desktop-first shell): 1280x800, 1440x900,
   1920x1080. The webServer block is left commented for local convenience and is
   wired so CI can opt in by setting E2E_WEB_SERVER=1 — CI may instead start the
   app itself and only point baseURL at it. Browsers are installed separately
   (`npx playwright install`); this config never assumes they are present.
   ============================================================================ */

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:3947';

export default defineConfig({
  testDir: './tests',
  // Each spec is independent; run files in parallel but keep a spec's own steps
  // serial so the stepped flows (auth, vidya) stay deterministic.
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list'], ['html', { open: 'never' }]],
  timeout: 30_000,
  expect: { timeout: 7_500 },

  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // The surface is a single-locale desktop app; pin it so text selectors hold.
    locale: 'en-US',
    timezoneId: 'UTC',
    // Collapse the calm idle/entrance animations (the app honours reduced motion)
    // so the Vidya orb and panels settle immediately and are clickable/stable.
    contextOptions: { reducedMotion: 'reduce' },
    // NB: we deliberately do NOT grant a fake microphone. Vidya is voice-first
    // (opening the orb auto-starts listening), but a granted fake media stream
    // stays live and deadlocks CDP input (keyboard/click) in headless. With no
    // mic, getUserMedia rejects fast and the orb degrades to the typed composer —
    // which is the realistic no-mic path and keeps input responsive.
  },

  projects: [
    {
      name: 'desktop-1280',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'desktop-1440',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'desktop-1920',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1920, height: 1080 } },
    },
  ],

  // CI may prefer to manage the server itself; opt in with E2E_WEB_SERVER=1.
  webServer: process.env.E2E_WEB_SERVER
    ? {
        // Run the web surface on the harness port. Adjust the cwd if the
        // workspace layout changes; this points at surfaces/web from e2e/.
        command: 'npm run dev -w @classess/web -- --port 3947',
        cwd: '..',
        url: BASE_URL,
        timeout: 120_000,
        reuseExistingServer: !process.env.CI,
      }
    : undefined,
});
