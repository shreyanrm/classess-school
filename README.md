# Classess School

An agentic academic intelligence platform — the first institutional citizen of the Dot eVentures education ecosystem. One connected system that observes, interprets, recommends, coordinates, and measures across the academic loop: Plan → Teach → Observe → Assign → Assess → Evaluate → Support → Communicate → Improve.

This repository is the **Ring 0 base** plus a live **v4 home shell**: the spine contracts, the secure core, the canonical data substrate, and a calm, conversation-first Vidya home built on the v4 brand.

## Dossier

The standing specification lives at the repo root:

- `00-START-HERE.md` — entry point and kickoff.
- `01`–`10` — vision, laws, architecture, build breakdown, flow, data model, the v4 brand, pages, the workflow playbook, and the Ring 0 brief.
- `classess-design-system/` — the canonical v4.1 brand kit (the source the React design system is ported from).

## Build

The build is documented in full at **`docs/BUILD.md`**. See also `docs/ARCHITECTURE.md`, `docs/SECURITY.md` (the twelve invariants and how this build honors each), and `docs/RING0-STATUS.md`.

### Layout

```
contracts/            single source of truth — events, evidence, OpenAPI, db schema, tokens (TypeScript)
packages/
  design-system/      the v4 brand ported to React — tokens, components, the spotlight cards, motion
surfaces/
  web/                the Vidya conversation-first home (Next.js)
spine/                the secure core — identity, gateway, event-store (FastAPI)
db/                   canonical Postgres migrations (PII vault segregated from the event store)
modules/              capability modules (Ring 1+)
ops/                  provisioning records + env var inventory (names only; values via Infisical)
docs/                 the build documentation
```

### Run

```bash
npm install                 # installs the TypeScript workspaces
npm run build:contracts     # build the contracts package
npm run build:ds            # build the design system
npm run dev                 # start the Vidya web home
```

FastAPI spine services run per `spine/README.md`.

> Secrets are environment-only, named `clss.<app>.<env>.<purpose>`, placed in Infisical by the founder, and never committed. See `ops/ENV.md`.
