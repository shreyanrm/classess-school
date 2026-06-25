# Classess School v3 — Build Dossier

**This is the single source of truth for the v3 build.** It supersedes every prior
spec — the platform document (`classess-school.html`), the earlier 11-section
dossier (`classess-vision.md`), the scattered repo docs (`SLICE*.md`, `RING2.md`,
`COVERAGE.md`, `ROADMAP.md`, `READINESS.md`), and the earlier `classess-v3-full-page-spec.md`.
Where any of those conflict with this set, **this set wins.** Read in order, then build.

> v3 is the product/codebase generation (v2.0.1 → v3). v4.1 is the design system
> applied to it. The two version numbers are independent and both correct.

---

## What you are building

Classess School — an **agentic academic intelligence platform**, the first
institutional citizen of the Dot eVentures education ecosystem. Four role surfaces
(Admin, Teacher, Student, Parent) over one shared spine. Production-grade from line
one: no MVP, no phases, no stubs, no partial development. The full capability
surface is the target; sequence is about order, never subtraction.

This is a **makeover + completion build**, not a greenfield rewrite and not a thin
patch. There are three real inputs and you reconcile them into one product:

1. **v2 (the current live app)** — feature-rich and validated by real institutions,
   but visually dated (coral/cream, Fraunces), dashboard-heavy, module-grid homes,
   modal- and table-heavy. **Take its flow and coverage; discard its visual language
   and its dashboard-first information architecture.** The v2 audit is in `01`.
2. **The existing repo** — Ring 0 live on Supabase (40 tables, PII vault segregated),
   the Student⇄Teacher loop running, Vidya live, the v4 design tokens in place, but
   most module engines unsurfaced and ~93 of 136 surfaces unbuilt or thin. **Treat
   it as substrate: keep what is correct, complete what is partial, fix the drifts
   named in `03`.**
3. **The vision** — independence-aware mastery, the ten-gap engine, generate-and-verify,
   the proactive loop, Vidya as the front door, evidence drawers, plain-language
   mastery, the assistance ladder. **This is the intelligence the makeover threads
   through every v2 flow.**

The result: every screen v2 already has, re-expressed on the v4.1 design system,
made calm and powerful, with the platform's intelligence surfaced inside it.

---

## The golden rules (true on every screen, every commit)

1. **One screen, one intention, one next action.** The home is never a wall of
   charts or a module grid. v2's "My Workspace" tile grid and "Principal Dashboard"
   are **deleted as homes** — the home is conversation-first (see `05`).
2. **v4.1 only.** Every colour, type ramp, space, radius comes from the token layer.
   No coral, no cream, no Fraunces/Inter/JetBrains. No drop shadows, ever. No generic
   defaults, no framework base styles. (`04`)
3. **Intelligence is visible and explainable.** Mastery is shown as independent vs
   support-dependent in plain language — never a raw score or the formula. Every
   recommendation carries evidence, confidence, owner, due date, and a "why am I
   seeing this." Every conclusion has an evidence drawer. (`02`, `10`)
4. **Human authority on anything consequential.** Send, submit, publish, delete,
   charge, grade — all pass through a person via the approval control. AI prepares;
   people decide. (`02`, `11`)
5. **The twelve security invariants hold on every merge.** PII vaulted, opaque UUID,
   every call through the gateway, secrets env-only, event contract immutable from
   line one, consent gating every cross-context read, generate-and-verify with a
   confidence gate, the permission ladder, immutable audit, encryption + tenant
   isolation, the two tracks separated, confidentiality discipline. (`02`)
6. **Emit a clean attributed event for every meaningful action, from line one.** The
   intelligence can only ever learn from what was recorded. (`12`)
7. **One engine, one truth.** Mastery / gap / evidence logic lives in the Python
   spine behind the gateway. Surfaces call it; they never re-implement it in
   TypeScript. (`03`)
8. **Every page ships its empty, loading, error, offline, and permission-denied
   states.** Offline is a designed state for the core flows, not a failure screen. (`05`)
9. **Confidentiality scrub on every artifact.** No confidential codenames, no
   personal names, no board lock-in language, no plaintext secrets, dummy `₹X,XXX`
   pricing only. (`02`)

---

## How this dossier is organized

| File | What it fixes |
|---|---|
| `00-START-HERE.md` | This file — how to use the set, the kickoff prompt. |
| `01-vision-and-the-makeover.md` | The vision (compressed) + the v2 audit + the v3 makeover thesis. |
| `02-laws-invariants-confidentiality.md` | Altitude, the ten principles, the twelve invariants, the scrub, the central tension. |
| `03-architecture-and-the-circuit.md` | Three layers, the seam, the gateway, single-engine truth, the circuit fix, the secure core, rings→waves. |
| `04-design-system-v4.md` | v4.1 applied: tokens, motion, the coral→steel translation rules, do/don't. |
| `05-information-architecture.md` | The conversation-first home, the rail, the 136-surface map, navigation, the universal state model. |
| `06-surface-spec-student.md` | 33 student surfaces, full depth. |
| `07-surface-spec-teacher.md` | 49 teacher surfaces, full depth. |
| `08-surface-spec-admin.md` | 34 admin surfaces, full depth. |
| `09-surface-spec-parent.md` | 20 parent surfaces, full depth. |
| `10-component-library.md` | The shared component vocabulary + the v2→v4 component mapping. |
| `11-vidya-and-ai-fabric.md` | Vidya home, the orchestrator, the model router, generate-verify, capabilities, the permission ladder, Track 2. |
| `12-data-model-and-contracts.md` | The three store classes, canonical tables, the `/contracts` package, the event catalog, the PII rule. |
| `13-capability-modules.md` | The eleven capability modules: owns / emits / consumes / data / API / done. |
| `14-parallelization-and-waves.md` | Bounded-context worktrees, the dependency DAG, the wave schedule, agent roles, the two gates. |
| `15-master-checklist.md` | The exhaustive, grouped, parallelization-aware checklist with per-surface and per-module definitions of done. |
| `16-the-home-and-generative-ui.md` | The conversation-first home (every role) + the five-path generative-UI engine + the drawer/popup/button inventory + what automates + premium elevation. |
| `17-vidya-orb-voice-and-command.md` | The living floating orb, the Siri-style voice bloom, the Cmd-K command palette, keyboard shortcuts, and the **Crystallize** signature moment (replaces ignite). |
| `18-navigation-and-shell.md` | The thin butter-smooth expanding rail, the shell regions, routing, responsive. |
| `19-settings.md` | The structured settings area — ten sections + role-specific, behaviour rules. |
| `20-motion-and-signature.md` | The motion-lab vocabulary mapped to usage (the chosen defaults), the alive layer, Crystallize, performance + a11y. |

**Also in the bundle (not docs — build inputs):**
- `design-system/` — the full v4.1 kit (tokens, components, motion-lab, sample-page,
  brand-kit, fonts). The single source of truth for every primitive; consume it, never
  hardcode. Open `sample-page.html` for the target vibe and `motion-lab.html` for the
  motion vocabulary.
- `prototype/` — two runnable HTML references. `vidya-experience.html` (home · expanding
  rail · composer · floating orb · Cmd-K · voice bloom · a generative component taking
  shape · the Crystallize moment) and `signature-and-motion.html` (the three signature
  options + the favourite motions). Build the React app to match their shape, motion, and
  feel.
- `components-react/` — reference React implementations of the hardest visual pieces
  (orb, voice bloom, command palette, expanding rail, conversation home, generative
  surface, Crystallize node). Port the rest of `10` to React the same way.

**Read order:** `00 → 01 → 02 → 03 → 04 → 05`, then `16 → 17 → 18 → 19 → 20` (the home,
Vidya's orb/voice/command, the shell, settings, and motion — the experience layer), then
`12` and `13` (the contracts and modules you bind to), then `14` (how to fan out), then
the surface specs `06`–`09`, the component library `10`, and the Vidya/fabric spec `11`
as you build each lane. `15` is the running ledger you keep green.

---

## The kickoff prompt (paste to begin)

> You are the build agent for Classess School v3 — an agentic academic intelligence
> platform and the first institutional citizen of the Dot eVentures education
> ecosystem. You build the entire stack: UI, backend, AI, databases, authentication,
> integrations. Production-grade from line one — no MVP, no stubs, no partial
> development.
>
> Your standing context is this dossier (`00`–`15`). Read it in order first. It is
> the single source of truth and supersedes all prior specs and repo docs.
>
> This is a makeover + completion build. The current repo is your substrate: keep
> what is correct (Ring 0, the live spine, the v4 tokens, the working loop), complete
> what is partial, and fix the named drifts in `03` (the home shape, the duplicated
> TS engine, the bypassed gateway/identity, the unsurfaced modules). The v2 app gives
> you flow and coverage; you re-express it entirely on the v4.1 brand with the
> platform's intelligence threaded through. v2's visual language and dashboard-first
> homes are discarded.
>
> Non-negotiables: the twelve security invariants in `02` hold on every merge. One
> engine, one truth — mastery/gap/evidence live in the Python spine behind the
> gateway; surfaces never re-implement them. Every call through the gateway; auth
> through the identity service; clean attributed events from line one; consent gating
> every cross-context read; generate-and-verify with a confidence gate; the permission
> ladder with human approval on anything consequential. UI on v4.1 tokens only — no
> coral, no cream, no Fraunces, no shadows, no generic defaults. Confidentiality
> discipline: never name the confidential orchestrator, never leak codenames or
> personal names, never use board lock-in language, dummy `₹X,XXX` pricing only.
>
> Method (`14`): contracts before parallel work. Decompose by bounded context; run
> agents in their own git worktrees against the shared `/contracts`. The secure core
> gets your most rigorous passes. Every merge passes two gates — verification
> (invariants, event contract, confidence gate, tests) and a confidentiality scrub.
> Build full-stack per slice — backend, AI, data, auth, and UI together against the
> locked contracts. Stop and report at every wave boundary; do not free-run the whole
> build.
>
> The experience bar (`16`–`20`, with runnable references in `prototype/`): the home on
> **every** role is conversation-first (the Gemini shape) — a calm greeting, one
> composer, proactive suggestion chips, an ambient bloom; no dashboard, no module grid.
> Vidya is a **generative-UI engine**: a request becomes an inline component that takes
> shape with real functionality and live visualizations, or it takes the action through
> the permission ladder, or it routes to the page and docks, or it routes and **guides
> the user with on-screen SVG overlays**. Build the **living floating orb** (drift +
> breathe) and the **Siri-style voice bloom** (the warm molten→ultramarine flow, alive
> and buttery) — they replace the current repo orb entirely; activate on orb-click,
> mic, hold-Space, and a **universal Cmd-K command palette**. The left rail is **thin
> and expands butter-smooth** (no lag, slide in/out, animate width + label transform
> only). Settings is a **structured area** (`19`). Motion uses the kit's motion-lab —
> rise-fill / fill-wipe buttons, spotlight / border-draw cards as defaults — and the
> ignite is replaced by the **Crystallize** signature moment (`17.5`, `20.2`). All of it
> on v4.1, European-spacey, no shadows, reduced-motion honoured. Match the prototypes'
> shape, motion, and feel; port `components-react/` and build the rest of `10` to the
> same bar.
>
> Provisioning: you are cleared to set up Supabase, install packages, integrate APIs.
> When you need a credential, name the env var (`clss.<app>.<env>.<purpose>`) and tell
> me to place it in Infisical — never handle secrets in plaintext. Record everything
> in `ops/`.
>
> Start with Wave 0 (`14`): reconcile the repo to this dossier — confirm the
> `/contracts` package, the event/evidence schema, the v4 token layer, identity, the
> gateway, the immutable event store; remove the duplicated TS engine; route every
> surface through the gateway. Pass the Wave 0 done-line, then stop and report before
> Wave 1. Begin.
