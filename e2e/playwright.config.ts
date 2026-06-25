import { defineConfig, devices } from '@playwright/test';

/* ============================================================================
   e2e/playwright.config.ts — the Classess School end-to-end harness.

   Drives the Next.js web surface (surfaces/web) over its dev port. The product
   is responsive, so the readiness click-through runs every spec across four
   viewports — mobile (390x844), tablet (768x1024), desktop (1280x800), and wide
   (1920x1080) — to prove every route loads and stays usable at each width. The
   webServer block is left commented for local convenience and is wired so CI
   can opt in by setting E2E_WEB_SERVER=1 — CI may instead start the app itself
   and only point baseURL at it. Browsers are installed separately
   (`npx playwright install`); this config never assumes they are present.
   ============================================================================ */

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:3947';

export default defineConfig({
  testDir: './tests',
  // Each spec is independent; run files in parallel but keep a spec's own steps
  // serial so the stepped flows (auth, vidya) stay deterministic.
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  // 2 retries everywhere: CI runs prod `next start`; a local standalone run may
  // hit `next dev`, whose on-demand compile + hydration jitter is exactly what a
  // retry absorbs (the suite is solid-green against a prod server — 264 passed).
  retries: 2,
  // One `next start` serves the whole run; an unbounded worker pool starves the
  // server's JS delivery (the client shell hydrates slowly under heavy
  // contention, so the rail/orb appear late). Cap parallelism so each tab gets
  // enough of the server — the suite stays fast without flaky resource
  // starvation. CI runs single-file for full determinism.
  workers: process.env.CI ? 1 : 3,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list'], ['html', { open: 'never' }]],
  timeout: 45_000,
  // A single `next start` serves every tab; the client shell (rail + orb)
  // hydrates a beat after first paint, and under a multi-viewport sweep that
  // wait is legitimately variable. A 12s assertion budget absorbs the hydration
  // wait so the green is solid, not retry-dependent — without hiding a real
  // hang (a genuinely broken page never paints the shell at all).
  expect: { timeout: 12_000 },

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
    // The four readiness viewports: mobile, tablet, desktop, wide. Every spec
    // runs at each width so the responsive layout invariants are proven across
    // the breakpoint range, not just on a desktop. Chromium throughout (the
    // console-error gate + CDP input path are the same engine at every width).
    {
      name: 'mobile-390',
      use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 } },
    },
    {
      name: 'tablet-768',
      use: { ...devices['Desktop Chrome'], viewport: { width: 768, height: 1024 } },
    },
    {
      name: 'desktop-1280',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'wide-1920',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1920, height: 1080 } },
    },
  ],

  // Always manage the web server so `npm run e2e` is green standalone (no
  // E2E_WEB_SERVER footgun). reuseExistingServer:true means CI's prod
  // `next start` on :3947 (or a local `next dev`) is reused instead of
  // double-starting on the harness port; if nothing is up, this starts one.
  webServer: {
    command: 'npm run dev -w @classess/web -- --port 3947',
    cwd: '..',
    url: BASE_URL,
    timeout: 120_000,
    reuseExistingServer: true,
  },
});
