# 03 · Architecture and the Circuit

## Three layers

- **Surfaces** — Admin, Teacher, Student, Parent. Thin; they compose views over
  modules and own no domain logic. **Vidya is the home itself** — the conversation-first
  front door every role lands in. The role's pages are destinations Vidya routes to
  and stays docked over.
- **Capability modules** — Classess School, feature-modular inside one deployable
  with clean internal boundaries (splittable into services later). Each owns its
  operational data and emits events.
- **Spine** — ecosystem-owned, built once, contracts immutable from line one. Role-
  and capability-agnostic: identity, ontology, event/evidence, the AI fabric,
  governance.

## The seam

Between every capability module and the spine: **emit attributed events up
(firehose), read governed scoped views down (faucet).** No app bulk-reads the
canonical store. This asymmetry gives independence, a clean security boundary, and
durable value at once. Non-deferrable past the first commit.

## Connection model — three wires

1. **Identity token** — who (one canonical person, consented).
2. **The gateway** — every call passes the wall; RBAC/ABAC scoped; schema-validated;
   audited.
3. **The event seam** — modules emit up, read governed views down.

Surfaces reach modules through gateway'd APIs. Modules reach intelligence through
events. Vidya reaches across by calling capabilities. That single circuit — identity
→ app → capability → event → intelligence → recommend → approve → execute → outcome →
learn — is the whole platform.

## The secure-core boundary

**Inside the wall (highest rigor):** identity, consent, gateway policy, the
event/evidence contract + store, the evidence/mastery/gap engines (the IP, and where
a wrong judgment is existential), the AI fabric router + agents + verification
substrate, governance/audit/secrets.

**Outside the wall (against contracts, no credentials, no platform store, reviewed +
scrubbed):** role surfaces, non-sensitive module logic, integration adapters. They
consume the API; they never build the orchestrator or the agents.

In this build Claude Code builds both sides as parallel agents; the boundary is an
architectural discipline (credential isolation, the gateway wall, the event seam),
not a human handoff. It holds even though one builder builds both sides, and it
future-proofs the moment humans join.

---

## The circuit — the four drifts v3 must fix

The current repo is a strong substrate but has four specific drifts that, left
unfixed, are exactly why "the final result won't match expectation." Fix all four in
Wave 0 before any new surface is built.

### Drift 1 — the home shape

**Found:** the repo moved Vidya to a floating orb and made the home a role-landing
with briefing cards (`surfaces/web/app/page.tsx` says so explicitly). v2 did worse —
module-grid / dashboard homes.

**Fix:** the home is **conversation-first** (the dossier mandate, `05`/`11`). Calm,
near-empty: a short greeting and one composer, a slim icon rail, history tucked behind
a button, the proactive layer as a few suggestion chips, components rendered inline
only when warranted, big tasks routed to their page with Vidya docked. The orb pattern
is retained only as the *docked* Vidya on deep workspace pages — never as the home
itself, never as a replacement for the conversation-first front door.

### Drift 2 — two engines, one truth

**Found:** the mastery/gap/evidence engine exists in Python (`spine/intelligence`) and
is re-ported into web `lib/engine.ts` for in-browser determinism — two sources of
truth, a drift the repo's own READINESS flags.

**Fix:** **one engine.** The mastery model, the ten-gap rules, evidence weighting, and
profile/graph projections live in the Python spine behind the gateway. Surfaces call
the gateway'd intelligence API; they never re-implement engine logic in TypeScript.
For offline, surfaces cache the *results* of engine reads (and a small
edge-SLM/deterministic fallback for the narrowly-scoped offline evaluation path), not
a re-implementation of the model. Delete `lib/engine.ts` as a parallel engine; replace
its call sites with gateway reads (with a typed client + cached read).

### Drift 3 — the bypassed gateway / identity

**Found:** surfaces sometimes call Supabase Auth and the DB directly instead of routing
through the identity service and the gateway (the repo's COVERAGE matrix flags this).

**Fix:** **every call through the gateway; auth through identity.** No app-local signup.
Surfaces hold no service credentials and never touch the canonical store. The server
API tier delegates to identity for tokens and to the gateway for every module call.
RBAC/ABAC is enforced at the wall.

### Drift 4 — unsurfaced modules

**Found:** most module engines live in the Python spine but are not surfaced in the web
("the circuit" gap); ~93 of 136 surfaces are unbuilt or thin.

**Fix:** every capability module is surfaced through a real, v4.1 page (or a docked
Vidya inline component) that calls the gateway. The 136-surface map (`05`) is the
target; the master checklist (`15`) tracks each to done. No engine ships without a
surface; no surface ships on mock data once its module is live.

---

## Stack (locked)

- **Surfaces:** Next.js (React + TypeScript) web + the classroom panel; Expo (React
  Native) native specified from line one, built in the wave after the web tree is
  green (offline-first contract defined now). PWA offline for the core flows on web.
- **Backend / spine + modules:** FastAPI (Python), typed, OpenAPI-documented,
  feature-modular in one deployable, splittable later.
- **AI fabric:** LiteLLM router (Track 1 / Track 2 config separated) · Langfuse
  observability · the orchestrator + capability registry + agent layer + the
  generate-and-verify substrate.
- **Data:** Supabase (Postgres + pgvector + Auth + Realtime + Storage) · Redis (cache,
  sessions, OTP, rate-limit). PII vault physically separate from the event store.
- **Integrations (FLUID):** LTI 1.3 · OneRoster 1.2 · xAPI/Caliper · QTI · SCORM ·
  Clever/ClassLink · Ed-Fi · CASE · MCP — contract-complete, adapters provider-pluggable.
- **Ops:** Infisical (secrets) · PostHog (analytics + flags + experiments) · Sentry ·
  CI/CD from the GitHub org. **No CDN dependencies in production** (fonts bundled via
  Fontsource).

### "Fully functional" vs parked providers

Every capability is built **contract-complete with a named, swappable adapter** — the
code is 100% done; the only missing thing is a credential placed in Infisical.
Capabilities whose live provider is a provisioning step (not code): live-class
video/recording media, FLUID live connectors, WhatsApp/SMS, board 3D/simulation media,
payments, GPU for Track 2 training, real OCR/proctoring providers. Each is built to
the contract with the adapter stubbed against the named env var; `13` and `15` list
exactly which adapter awaits which key. This is what "no partial development" means
here — complete code, pluggable provider — not "call a live provider with no key."

## Rings → waves

The old rings are preserved as the dependency spine; `14` expresses them as parallel
**waves** (what can run simultaneously once contracts land):

- **Wave 0 — reconcile + base:** the `/contracts` package, the v4 token layer, the data
  substrate, identity, the gateway, the immutable event store + event/evidence
  contract, secrets + CI — and the four circuit fixes above. Serial; settles before
  anything rides on it.
- **Wave 1 — the Student⇄Teacher loop:** both surfaces together end to end (the heart),
  lighting up coursework + evaluation, learning, the evidence/mastery/gap engines,
  content generate-verify, the workflow/permission runtime, the AI fabric router.
- **Wave 2 — Admin + Parent (parallel) + intelligence depth:** institution/policy,
  scheduling/continuity, the intelligence views, the proactive feed; the parent
  absolution engine + consent authority; communication, teacher growth.
- **Wave 3 — ecosystem scale + parked providers:** FLUID live connectors, comms
  lifecycle, multi-tenancy across group/franchise/programme/network, Track 2 models,
  native Expo, the live-media board.

The event contract is Wave 0 even though the intelligence that consumes it matures in
Waves 1–3. Emit from line one, consume as it matures.
