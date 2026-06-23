# @classess/e2e — end-to-end harness

Playwright end-to-end tests for the Classess School web surface (`surfaces/web`).
These drive the real Next.js app in a browser: the stepped auth flow, rail
navigation, the floating Vidya orb, the live `/api/school` persistence circuit,
and the responsive layout invariants at desktop widths.

The specs lean on the **stable `data-testid` hooks** already in the app
(`vidya-orb`, `vidya-panel`, `vidya-composer`, `vidya-composer-input`,
`vidya-type-instead`, `rail`, `rail-item` with `data-rail-href`, `role-landing`,
`loop-controls`, `loop-steps`, `auth-step` with `data-step`, `auth-continue`,
`auth-back`, `auth-social-google|apple|microsoft`). They never modify app code.

## One-time setup

```bash
# from the repo root
npm install                 # installs workspaces incl. @classess/e2e
npx playwright install      # downloads the browsers (Chromium etc.)
```

> The browsers are **not** bundled — `npx playwright install` must be run once on
> any machine (and in CI) before the tests can launch a browser.

## Running

Start the web app on the harness port (`3947`) in one terminal:

```bash
npm run dev -w @classess/web -- --port 3947
```

Then run the tests:

```bash
# from the repo root
npm run e2e                 # headless, all viewports
# or from this folder
cd e2e
npx playwright test         # headless
npx playwright test --headed
npx playwright test --ui    # interactive runner
npx playwright show-report  # last HTML report
```

### Let Playwright start the server for you

Set `E2E_WEB_SERVER=1` and Playwright will boot `surfaces/web` on port 3947
itself (see the `webServer` block in `playwright.config.ts`):

```bash
E2E_WEB_SERVER=1 npx playwright test
```

CI may prefer to manage the server and just point the harness at it:

```bash
E2E_BASE_URL=http://localhost:3947 npx playwright test
```

## Viewports

Three desktop projects run every spec: `desktop-1280` (1280×800),
`desktop-1440` (1440×900), `desktop-1920` (1920×1080). The responsive spec
asserts the rail / content / orb never overlap at each width.

## Demo mode vs. live circuit

The app defaults to **demo mode** (no Supabase, no `CLSS_DATABASE_URL`):

- **Auth** accepts any email/password and lands on the role home — the auth spec
  asserts the *stepped flow + structure*, so it passes either way.
- **Vidya** chat (`/api/vidya/chat`) degrades to a local responder without a
  provider key; the vidya spec **mocks** the route for deterministic assertions
  and also covers the degrade path.
- **Persistence** (`/api/school`) returns `{ persisted: false }` without a DB;
  the persistence spec asserts the **full POST→GET round-trip when the live
  circuit is on**, and the calm degrade contract otherwise.

To exercise the live persistence round-trip, run the app with `CLSS_DATABASE_URL`
set against a migrated operational schema.

## Files

- `playwright.config.ts` — baseURL `http://localhost:3947`, three desktop
  projects, optional `webServer`.
- `tests/helpers.ts` — shared steps (seed a demo session, complete sign-in, open
  the orb, reveal the typed composer).
- `tests/auth.spec.ts` — stepped sign-up (role→email→password) and sign-in
  (email→password), Back, social buttons.
- `tests/navigation.spec.ts` — every `rail-item` resolves (no 404); role landing
  renders, per role.
- `tests/vidya.spec.ts` — orb opens, accepts a typed message, routes a
  natural-language ask, degrades cleanly.
- `tests/persistence.spec.ts` — POST `/api/school` then GET returns the row.
- `tests/responsive.spec.ts` — orb + rail + content do not overlap at each
  viewport.
