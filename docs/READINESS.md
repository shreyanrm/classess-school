# Definition of "ready"

The bar the founder set. **Do not call the application ready until every item
here is built, wired, and verified** — not just present in the backend. Status
legend: ✅ done · 🟡 partial · ⬜ not yet.

## 1. First-run, onboarding & account creation
- ⬜ A real entry point: welcome → sign-in (phone-OTP shape) → role. The app must
  *begin* somewhere, not drop into a mock home.
- ⬜ **Account creation feels personalised and seamless.** It does **not**
  interrogate the user with forms about interests/likes/dislikes.
- ⬜ **Implicit profiling** — infer interests, strengths, preferences, and the
  data we need from behaviour and light conversational choices, not explicit
  questionnaires. The experience should feel like Vidya *getting to know you*.
- ⬜ **Consent / age-tier gated (non-negotiable):** implicit profiling depth is
  bounded by the DPDP consent + age tier (children's-data rules). We build the
  doors the law provides and never infer beyond the permitted tier. Profiling is
  transparent and revocable. (See `02-laws` invariant 6 + the DPDP note.)
- ⬜ Vidya guides onboarding conversationally and is docked throughout.

## 2. School setup (admin)
- 🟡 Blueprint wizard exists (`/admin/setup`) + `modules/institution` backend.
- ⬜ Setup **persists** — creates a real institution, structure, and roster that
  survives reload (local persistence layer until Supabase is provisioned).
- ⬜ Vidya assists setup (structure, roles, policies, roster) with human approval.

## 3. The full cold-start flow, stitched end to end
- 🟡 Academic loop runs at `/loop` (assign → attempt → mastery/gap → intervene →
  reassess → teacher sees it).
- ⬜ The whole journey connects: **set up → populate (classes + roster) → teach →
  loop → report**, with no dead ends between stages.

## 4. Vidya — autonomous, AI-native, assisting everywhere
- 🟡 Text orchestrator (Gemini tool-calling) wired into the home.
- ✅ Voice (speech-to-speech) working with the provider key.
- ⬜ Vidya assists *along the way* on every surface (onboarding, setup, teaching,
  learning, parent), docked and proactive, permission-laddered (never auto-fires
  consequential actions).

## 4b. Proprietary continuously-learning model (Track 2)
- 🟡 `spine/model-foundry` — the BASE: event→signal capture (PII-free, consent/age-tier
  gated), versioned datasets, curation/safety, eval harness, fine-tune/distill
  runner, registry with human-gated promotion into the Track 2 serving slot, the
  observe→learn loop. Real, tested pipeline.
- ⬜ Actual training run — needs a compute/GPU backend (env-configured). The runner
  degrades to a "no-compute plan" until attached. This is a provisioning step, not code.
- ⬜ Live wiring: model-foundry ← event-store signals, model-foundry → ai-fabric Track 2.

## 5. Consistency, UX & functionality (all pages)
- ⬜ Every page on v4 tokens, one accent per surface, shared shell identical.
- ⬜ Every page is relevant, with one clear intention and working controls.
- ⬜ Every Rail entry reaches a real page; no orphan pages, no dead links.
- ⬜ Empty / loading / error / offline states on every page.

## 6. Connections & integrations on point
- 🟡 Gateway hardening + module route registration (rate-limit, schema validation).
- ⬜ Surfaces consume one coherent data/engine flow (no web-TS vs Python drift).
- 🟡 FLUID connectors (LTI/OneRoster/xAPI/QTI/SCORM/Clever/Ed-Fi/CASE/MCP).

## 7. Platform coverage (d1–d22, from classess-school.html)
Track against `docs/` coverage audit. Notable gaps to close before ready:
- 🟡 d6 planning + teacher diary (backend in; pages pending)
- 🟡 d7 classroom / live class (backend in; pages pending)
- 🟡 d8 attendance (backend in; pages pending)
- 🟡 d10 exam ops · d13 mocks · d9 group balancing (backend extending)
- ⬜ d18 communication / messaging **UI** (backend in; no surface yet)
- 🟡 d5 dedup + mind-maps · d12 misconception detonation (done, tested)

## 7b. Ontology depth & hyperlocalisation
- ✅ Ontology contract (board→…→topic→prereq→outcome→competency→equivalence).
- ✅ Ingestion pipeline + prerequisite steward (propose→confirm) + cross-board
  equivalence + pgvector embeddings.
- 🟡 Seeded narrow (one board, Class 10, Mathematics + Physics). **Load real
  curriculum across boards/grades/subjects** (needs a doc-understanding provider
  + curriculum sources) and exercise cross-board equivalence with 2+ boards.
- ✅ Hyperlocalisation config (language/region/calendar as inherited policy keys,
  board-agnostic) + multilingual / code-switching translation (subject terms
  preserved).
- ⬜ **Hyperlocalised content *delivery*** — same concept generated/adapted for
  board+language+region+calendar+culture ("relevance, not translation"), threaded
  through content generation.
- ⬜ **Surfaces** — a curriculum/ontology admin view; language/region/calendar
  config UI; hyperlocalised content shown to learners.

## 8. Quality gate (must be green to ship)
- ⬜ `npm run ci` green: typecheck → vitest → pytest (all modules) → `next build`.
- ⬜ Full click-through of every role's flow, verified working in the running app.
- ⬜ Confidentiality scrub clean; secrets env-only; v4 brand only.

---
**Rule:** "ready" is asserted only when §1–§8 are ✅ and the click-through passes.
Until then, report honestly as partial.
