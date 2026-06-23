# Classess School — Ring 0 Build

The master build document. It describes what was built in Ring 0, where every
piece lives, what each module owns / exposes / consumes, how to run the whole
thing locally, and the contract boundary that lets the lanes build in parallel.

---

## 1. What Classess School is

Classess School is an agentic academic intelligence platform — the first
institutional citizen of the Dot eVentures education ecosystem. It is one
connected system that observes, interprets, recommends, coordinates, and
measures across the academic loop (Plan, Teach, Observe, Assign, Assess,
Evaluate, Support, Communicate, Improve). It is board-agnostic by construction
(curriculum is ingested and mapped, never hard-coded), AI-native (intelligence
is the substrate, not a chat button), and built so that human authority gates
every consequential action. The home itself is a conversation-first assistant
that routes to role destinations and stays docked over them, rather than a menu
the user navigates.

---

## 2. Ring 0 scope

Ring 0 is the secure base, built once and completely, before any feature. It is
not an MVP and not a stub: every line is production-shaped, and the event
contract is immutable from the first commit. Ring 0 contains exactly six things,
in dependency order:

1. Repository, secrets convention, and workspace wiring.
2. The `contracts` package — the single source of truth every later lane binds to.
3. The operational data substrate — Postgres migrations encoding the PII rule.
4. The identity service — canonical user, membership, RBAC/ABAC inputs, consent.
5. The API gateway — the one wall: token verification, policy, validation, audit, routing.
6. The immutable event store — append-only write path plus the consent-gated read path.

A consumable design system and a conversation-first web surface are also built
on the Ring 0 contracts to prove the boundary end to end. Feature modules
(the Student/Teacher slice and beyond) are Ring 1 and are deliberately not
started here.

---

## 3. Monorepo layout

```
classess-school/
  contracts/                  SINGLE SOURCE OF TRUTH (TypeScript, Zod + OpenAPI 3.1)
    src/
      events/                 immutable v1 event + evidence schemas
      openapi/                per-capability API specs (identity, gateway, event-store)
      db/                     typed mirror of the canonical DB schema
      tokens/                 v4.1 design tokens (typed re-export of tokens.json)
  packages/
    design-system/            the v4 brand ported to React — tokens, components, motion
  surfaces/
    web/                      the conversation-first web home (Next.js 15, React 19)
                              (Slice 1) Teacher + Student surfaces; (Slice 2) Admin surface + Vidya voice UI
                              (Slice 3) Parent surface (partnership + pride, consent-gated, proof artifact)
  spine/                      THE SECURE CORE (FastAPI) — founder + Claude Code only
    identity/                 canonical user (PII vault), membership, consent, token mint
    gateway/                  THE WALL: token verify, RBAC+ABAC, validate, audit, route
    event-store/              immutable append-only write path + consent-gated read path
    intelligence/             (Slice 1, A3) evidence -> mastery -> gap projection engine
    ai-fabric/                (Slice 1, A4) model router + generate-and-verify substrate
                              (Slice 2) app/voice.py — Vidya speech-to-speech (Gemini Live), ephemeral-token mint
                              (Ring 2) app/track2.py — Track 2 proprietary/edge SLM adapter (separate config + ownership)
    workflow/                 (Slice 1, A5) seven-step loop + permission-ladder runtime
    integration/              (Ring 2, A6) FLUID two-way standards bridge + connector-health
    governance/               (Ring 2, A7) immutable audit, break-glass, AI control centre, consent/lineage, child-safety, tenancy
    feature-store/            (Ring 2, A3) derived versioned features + reproducible prediction (consumes intelligence)
  db/
    migrations/               seven ordered Postgres migrations (the canonical substrate)
  modules/                    capability modules (Ring 1+)
    coursework/               (Slice 1, B6) CORE evaluation engine + paper generation
    learning/                 (Slice 1, B7) pose->reveal, assistance ladder, practice, revision
    content/                  (Slice 1, B3) governed content repository + generate-and-verify
    institution/              (Slice 2, B1) structure ladder, provisioning wizard, policy, multi-tenancy
    scheduling/               (Slice 2, B2) calendar, timetable solver, substitution ladder, pacing
    learner-record/           (Slice 3, B8) evidence-linked profile, portfolio, verifiable credentials
    communication/            (Slice 3, B9) bounded companion, safeguarding, hub, parent partnership, translation
    intelligence-views/       (Slice 3, B11) semantic layer, dashboards, study quadrant, prediction, ask-anything
    ontology-ingestion/       (Ring 2, A2) curriculum ingestion + prerequisite-edge steward + cross-board equivalence
    teacher-growth/           (Ring 2, B10) private classroom-interaction metrics, coaching, quality review, continuity
  ops/                        provisioning records + env var inventory (names only)
  docs/                       this build documentation
```

`spine/` and `contracts/` are the secure core and are never handed to the
developer lanes. `surfaces/` and the non-sensitive parts of `modules/` are the
developer lanes, built against `contracts/` only.

---

## 4. The modules

### 4.1 `contracts` — `@classess/contracts`

The single source of truth. A TypeScript package (Zod schemas plus typed
OpenAPI 3.1 objects) that every later lane and service binds to.

- Owns: the immutable v1 event/evidence contract; the OpenAPI specs for the
  three spine capabilities; the typed description of the canonical DB schema;
  the v4.1 design tokens.
- Exposes: subpath entry points `@classess/contracts`, `.../events`,
  `.../openapi`, `.../tokens`; the `EventEnvelope`, `EmitEventInput`,
  `EventBody`/`EventType` discriminated union, `AttemptPayload` (with the
  `AttemptMode` independent-vs-supported flag and the six-level
  `AssistanceLevel` ladder), `MasteryDimensions`/`MasteryReading`/`MasteryWeights`
  (Performance x Reliability x Independence x Difficulty x Recency x Consistency,
  never collapsed at the contract level), the closed `GapType` union of ten gap
  types, `Verification` and `PermissionRung` (defined now for Ring 1),
  `identityOpenApi`/`gatewayOpenApi`/`eventStoreOpenApi`, `canonicalSchema`/`canonicalTables`,
  and `tokens`.
- Consumes: nothing. It is the root of the dependency graph.
- Notes: the event store OpenAPI intentionally has no update or delete
  operation (append-only). All three specs require the bearer scheme. The `db`
  module is the typed mirror of `db/migrations` and must stay consistent with
  it. Built to `./dist` via `tsc`; consumers that typecheck need `dist` present.

### 4.2 `packages/design-system` — `@classess/design-system`

The canonical v4.1 brand ported into a consumable React package.

- Owns: the verbatim token port (`tokens.css`, light and dark, no value
  changes); the component library (`components.css`); the card-hover and motion
  treatments (`motion.css`); font loading (`fonts.css`); typed, accessible,
  token-driven React components (Button, Card, SpotlightCard, TiltCard, Matrix,
  SubjectCard, Stat, Tag, Badge, ProgressBar, IgniteDot, ConfidenceBand, Avatar,
  Input, Textarea, Composer, SuggestionChip, Icon, ThemeProvider) and the hooks
  they ride on (useSpotlight, useTilt, useMagnetic, useCountUp, useReducedMotion).
- Exposes: the package entry (components + hooks + types) and
  `@classess/design-system/styles.css`.
- Consumes: nothing from the workspace; declares (not installed) lucide-react,
  the Fontsource font packages, and react/react-dom as peers.
- Notes: the only box-shadow in the system is the functional focus ring (never a
  drop shadow); ultramarine is excluded from the subject-accent type so the
  signature colour can never be used as a subject colour; all motion honors
  `prefers-reduced-motion`. Google Sans Flex is not on Fontsource and falls back
  to Poppins; the self-host route is documented in the package README. Consuming
  apps import the stylesheet once at the root and wrap in `<ThemeProvider>`.

### 4.3 `surfaces/web` — `@classess/web`

The conversation-first web home, a Next.js 15 App Router app (TypeScript,
React 19).

- Owns: the home (calm, near-empty, one centred Composer with a few quiet
  suggestion chips as the proactive layer); the message thread and inline-result
  rendering; the slim icon-only left rail; the two destination pages that prove
  big-task routing (`/insights` renders a tight matrix of stat cards, subject
  cards, and a plain-language mastery view; `/proactive` is the recommendation
  feed where each item shows evidence, confidence band, owner, due date,
  consequence, and an Approve/Adjust/Decline control that never auto-fires); and
  first-class empty, loading, error, offline, and not-found states.
- Exposes: nothing (it is a leaf surface).
- Consumes: `@classess/design-system` (components, types) and TYPES only from
  `@classess/contracts` (MasteryBand, GapType, and the design-system Confidence
  and SubjectAccent types).
- Notes: the surface never touches the event store or PII vault directly.
  `lib/runtime.ts` declares the gateway env var names and gates the live path;
  until the gateway is provisioned the app degrades to `lib/mock.ts` behind the
  same interface. `app/_components/respond.ts` is the local stand-in for the live
  generate-and-verify turn responder and carries the confidence gate and the
  Prepare-not-Execute posture; swap it for a gateway call when wired.

### 4.4 `spine/identity`

The sole PII holder and the source of identity tokens.

- Owns: the PII vault (`vault.users`); minting of gateway-verifiable RS256
  tokens (holds the private signing key); time-bound AppMembership resolution;
  consent capture and checks. The `canonical_uuid` is generated opaque/random and
  never derived from PII; no response model returns PII.
- Exposes: `POST /v1/identity/auth/otp/start`, `POST .../auth/otp/verify`,
  `POST .../auth/token/introspect`, `GET .../memberships/resolve`,
  `POST .../consent/check`, `POST .../consent/grant`, `POST .../internal/users`.
- Consumes: the contracts identity OpenAPI and event primitives; the vault and
  consent migrations.
- Notes: the private signing key lives only here; the matching public key is
  distributed to the gateway and event store for verification.

### 4.5 `spine/gateway`

The wall. Every routed call passes through it.

- Owns: token verification; a deny-by-default RBAC+ABAC policy engine
  (scope-containment ABAC, explicit baseline rule table, unknown operation = not
  routable); the `X-Consent-Purpose` requirement for cross-context reads;
  immutable audit of every decision (allow and deny); routing to upstreams; and
  the two structurally separate track config sections (Track 1 external LLM
  routing, Track 2 proprietary/edge reserved slot).
- Exposes: `POST /v1/route/{capability}/{operation}`, `POST /v1/policy/evaluate`,
  `GET /v1/tracks`.
- Consumes: the contracts gateway OpenAPI; the identity and event-store upstreams.
- Notes: the gateway is the only component that operates as the Supabase service
  role; RLS denies everything else.

### 4.6 `spine/event-store`

The immutable behavioral store and its governed read path.

- Owns: the INSERT-only write path (no update or delete endpoint exists);
  full validation against the event contract (discriminated union, attempt
  independent-vs-supported coherence, mastery/gap shapes); rejection of PII keys
  in payloads; and reads ONLY through the consent+purpose-gated path mirroring
  `platform.read_events` (empty set / 404 when unsatisfied, never a leak).
- Exposes: `POST /v1/event-store/events`, `GET /v1/event-store/events`,
  `GET /v1/event-store/events/{event_id}`.
- Consumes: the contracts event-store OpenAPI and event schemas; the events and
  governed-views migrations.
- Notes: it normalizes the integer `schema_version` in the DB to the contract
  string `"v1"` at the boundary so the API always speaks the contract.

### 4.7 `db` — canonical / platform substrate

Seven ordered Postgres migrations that encode the security model structurally.

- Owns: three schemas — `vault` (PII, most restricted), `platform`
  (behavioral/canonical, opaque `canonical_uuid` only), `audit` (immutable);
  the tables `vault.users`, `platform.app_memberships`, `platform.consents`,
  `platform.events` (append-only, immutable, monthly range-partitioned), and
  `audit.audit_log`.
- Exposes: `platform.read_events(canonical_uuid, purpose)` (the only governed
  read path), `platform.satisfied_purposes(canonical_uuid)`, and the
  `platform.deny_mutation()` immutability trigger function.
- Consumes: the data-model spec and the Ring 0 brief data model.
- Notes: there is deliberately no SQL foreign key across the vault->platform
  boundary, so deleting a vault row severs identity while events remain
  unlinkable. Migrations are idempotent and ship with the 2026-06 and 2026-07
  partitions plus a default catch-all.

---

## 5. Running it locally

> Do not run installers or builds inside an individual lane during the parallel
> build; the orchestrator installs and builds centrally. The steps below are the
> central, one-time setup. Secrets are environment-only — see `ops/ENV.md`.

### 5.1 TypeScript workspaces (contracts, design system, web)

```bash
# from the repo root
npm install                 # installs all TypeScript workspaces once
npm run build:contracts     # build @classess/contracts to ./dist (required before web typecheck)
npm run build:ds            # build @classess/design-system
npm run dev                 # start the web home (next dev)
```

The web surface imports only TYPES from contracts (erased at compile), so
`next dev` runs even before contracts are built; `tsc --noEmit` and `next build`
require `contracts/dist` to exist first.

### 5.2 The database substrate

Apply the seven migrations in order against a fresh Supabase Postgres
(`db/README.md` has the full Supabase CLI and `psql` recipes). The connection
string resolves from the environment only:

```bash
psql "$DATABASE_URL" \
  -f db/migrations/0001_extensions.sql \
  -f db/migrations/0002_pii_vault.sql \
  -f db/migrations/0003_memberships_consent.sql \
  -f db/migrations/0004_events.sql \
  -f db/migrations/0005_audit.sql \
  -f db/migrations/0006_governed_views.sql \
  -f db/migrations/0007_rls.sql
```

### 5.3 The FastAPI spine services

Install each service's `requirements.txt` centrally, then run the three apps.
With nothing configured they start in a clearly-labelled degraded mode
(in-memory stores, logger audit sink, unsigned dev tokens) so the contracts are
exercisable without a live Supabase. Suggested ports:

```bash
# identity
cd spine/identity    && uvicorn app.main:app --reload --port 8001
# event-store
cd spine/event-store && uvicorn app.main:app --reload --port 8002
# gateway (routes to the two above)
cd spine/gateway     && uvicorn app.main:app --reload --port 8000
```

Point the gateway's upstream env vars at identity (8001) and event-store (8002).
Provide the env vars in `ops/ENV.md` to move each service onto the production
path; the unsigned dev token is rejected the moment a real public key is present.

---

## 6. The contract boundary (why the lanes run in parallel)

The `contracts` package is the gate. The instant it lands, every other lane
builds against it at once:

- The web surface binds to the OpenAPI specs and event types and mocks anything
  not yet live behind the same interface.
- The design system is pure presentation against the tokens.
- The spine services mirror the Zod schemas in Pydantic and the migrations in
  the typed `db` module.
- The migrations are the structural truth the typed `db` module mirrors.

Because every lane shares one frozen contract and writes only inside its own
directory, agents on disjoint modules never collide. The same seam that makes
the architecture safe — emit attributed events up, read governed scoped views
down, every call through the gateway — is the seam that makes the parallelism
safe. See `docs/ARCHITECTURE.md` for the layers and the circuit, and
`docs/SECURITY.md` for the twelve invariants and where each is honored.

---

## 7. Ring 1 — Slice 1: the Student ⇄ Teacher core loop

Ring 1 builds in vertical slices. The first and central slice is the
Student ⇄ Teacher loop: a teacher assigns and assesses; a student attempts with
the independent-vs-supported flag captured at the act; the attempt becomes an
immutable event; the intelligence engine weighs that evidence across six mastery
dimensions and classifies any gap among ten types; a governed intervention is
recommended (never auto-fired); the student reassesses unaided; mastery updates
only on fresh evidence; and the teacher sees it in plain language.

It lights up six modules plus both surfaces, built to production depth on a
narrow path — one example board, Class 10, Mathematics and Physics — board-
agnostic in the contract:

- `spine/intelligence` (A3) — the CORE evidence/mastery/gap engine.
- `spine/ai-fabric` (A4) — the model router and the generate-and-verify gate.
- `spine/workflow` (A5) — the seven-step loop and permission-ladder runtime.
- `modules/coursework` (B6) — the CORE three-mode evaluation engine.
- `modules/learning` (B7) — pose→reveal, the assistance ladder, practice, revision.
- `modules/content` (B3) — the governed content repository and generation.
- `surfaces/web` — the Teacher and Student surfaces and the live `/loop` page.

The contracts package gained five Slice 1 surfaces (`contracts/src/ontology`,
`evaluation`, `assistance`, `recommendations`, `ai`) as new files; no Ring 0
event/evidence file was touched.

**The full Slice 1 build — the loop diagram, each module's owns/exposes/consumes,
the generate-and-verify confidence gate, the permission ladder and human-final
marking, how to run the surfaces and the Python tests, and the env var additions
— is documented in `docs/SLICE1.md`.** Checkpoint 1 status (does the loop run end
to end, what is production-grade now, what awaits live provisioning) is in
`docs/SLICE1-STATUS.md`.

---

## 8. Ring 1 — Slice 2: the Admin surface and Vidya voice

Slice 2 builds the institutional layer above the learning loop — the surfaces and
modules an administrator works in — and gives Vidya a voice. The Admin surface is
a morning briefing, not a dashboard: it surfaces only what needs a human decision
(manage by exception) and every item carries evidence, a confidence band, the
owner, a due date, the consequence, and a why-am-I-seeing-this line. No structural
or operational change auto-commits, and autonomy is bounded and revocable.

It adds two capability modules, one spine capability, and the Admin + voice
surfaces:

- `modules/institution` (B1) — the board-agnostic structure ladder, the
  PREPARE-class provisioning wizard, policy inheritance, and logical multi-tenancy.
- `modules/scheduling` (B2) — the academic calendar, the dynamic timetable solver,
  the six-level substitution ladder (never an unsupervised free period), and pacing.
- `spine/ai-fabric/app/voice.py` (A4) — the Vidya speech-to-speech adapter (Gemini
  Live), with an ephemeral-token mint so the raw key never leaves the server, gated
  by the same confidence gate and permission ladder.
- `surfaces/web/app/admin` — the Admin morning briefing, blueprint wizard,
  substitution cover, intelligence matrix, and governance / break-glass surface.
- `surfaces/web/app/api/voice` + `lib/voice.ts` — the server-only token route and
  the typed voice client; voice degrades calmly to "unavailable" with no key.

**The full Slice 2 build — the manage-by-exception model, each module's
owns/exposes/consumes, the human-authority gates (timetable / substitution never
auto-commit, break-glass), the ephemeral-token model for voice, how to run, and
the env additions including `clss.aifabric.dev.gemini_api_key` — is documented in
`docs/SLICE2.md`.**

---

## 9. Ring 1 — Slice 3: the Parent surface, learner record, communication, intelligence views

Slice 3 builds the **relationship and composition** layer: the surface a parent
works in (partnership and pride, never surveillance), the record that composes a
learner's evidence into an evidence-linked profile and portable, verifiable
credentials, the communication layer that runs child-safety on every free-text
surface, and the intelligence views that turn the proactive loop into calm,
explainable dashboards through one governed semantic layer.

It adds three capability modules and the Parent web surface:

- `modules/learner-record` (B8) — the consent + purpose-gated, denied-by-default
  read of governed evidence views composed into a plain-language profile (never a
  number), a provenance-required portfolio, and verifiable / portable /
  learner-controlled credentials (never faked without a signing key). Authors no
  mastery, computes no score.
- `modules/communication` (B9) — the bounded companion, the communication hub, the
  parent-teacher partnership channel, translation, and **safeguarding**: the
  child-safety subsystem that screens every free-text message, allows no
  unmonitored channel, and escalates a crisis to a qualified human (never
  auto-resolved).
- `modules/intelligence-views` (B11) — the semantic layer (one metric defined
  once, resolved the same everywhere), dashboards whose alerts ARE spine
  workflow recommendations (full provenance, never auto-fire), the study quadrant,
  prediction, target analytics, and a consent-gated, safety-screened ask-anything.
- `surfaces/web/app/parent` — the Parent surface: Today (calm actions this week),
  Child view (one timeline per child, the consent-aware Child switcher, the Proof
  artifact), Reports, and Together. Consent is enforced in data
  (`selectChildData()` returns null for an unconsented child), so behavioural data
  cannot leak through the UI.

**The full Slice 3 build — the consent-authority + partnership model, each
module's owns/exposes/consumes, child-safety on every free-text surface, the proof
artifact, the human-authority gates, how to run, and the env names — is documented
in `docs/SLICE3.md`.**

---

## 10. Ring 2 — the standards bridge, ontology, growth, governance, the feature store, Track 2, and the Ring 2 surfaces

Ring 2 builds the connective and governing tissue that lets the platform live on top
of systems schools already run, keep its curriculum graph alive, grow its teachers,
govern its most powerful surfaces, and turn the immutable event log into reproducible
features and forecasts. It binds to the same frozen `@classess/contracts` boundary
and the same twelve invariants, and the two model tracks (external / open-standard
Track 1 and proprietary / edge Track 2) stay structurally separate in config and
ownership throughout.

It adds two spine capabilities, one derived spine store, the Track 2 AI-fabric slot,
two capability modules, and four web surfaces:

- `spine/integration` (A6) — the FLUID two-way standards bridge: a connector
  framework + connector-health monitoring (states with hysteresis) and interface-
  complete adapters for LTI 1.3, OneRoster 1.2, xAPI, Caliper, QTI, SCORM, Clever,
  ClassLink, Ed-Fi, CASE, and an MCP surface, mapping everything to opaque,
  board-agnostic ontology + canonical identity. Adapters hold no credentials;
  consequential effects are prepared and approval-gated.
- `spine/governance` (A7) — immutable audit, break-glass, the AI control centre
  (Track 1 / Track 2 separated, confidence-gate stats, emergency disable),
  consent / retention / lineage, the child-safety subsystem on every free-text
  surface, and tenant isolation (default deny, read-down only).
- `spine/feature-store` (A3, Ring 2) — derived, versioned, point-in-time-correct
  features and reproducible trajectory / exam-readiness / risk predictions, built by
  replaying the immutable event log and consuming `spine/intelligence` through a
  single audited seam (the engine is never modified).
- `spine/ai-fabric/app/track2.py` (A4) — the Track 2 proprietary / edge SLM adapter,
  kept separate from Track 1, behind the same confidence gate, on the RECOMMEND rung,
  with no existing router / verify / voice / registry behavior changed.
- `modules/ontology-ingestion` (A2) — curriculum ingestion into the typed ontology
  graph (nodes always drafts), the prerequisite-edge steward (propose →
  human-confirm), and the symmetric, board-agnostic cross-board equivalence registry.
- `modules/teacher-growth` (B10) — the four deterministic classroom-interaction
  metrics, private teacher-first coaching signals, a human-owned quality-review state
  machine, and the continuity / handover note — never a league table, AI never
  decides employment.
- `surfaces/web/app` — the connector hub (`admin/integrations`), the AI control
  centre (`admin/control-centre`), the private teacher growth surface
  (`teacher/growth`), and the group → region → campus network rollup
  (`admin/network`), all on the v4 brand with Vidya docked.

**The full Ring 2 build — each module's owns/exposes/consumes, the two-track
separation made concrete, how to run the Python suites and the web surfaces, the
build-environment notes, and the env names — is documented in `docs/RING2.md`.**
