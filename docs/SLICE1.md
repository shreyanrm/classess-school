# Classess School — Slice 1: the Student ⇄ Teacher core loop

This is the build document for Ring 1, Slice 1 — the heart of the platform.
Where `docs/BUILD.md` describes the secure base (Ring 0), this describes the
first vertical slice cut down through the spine and up to both surfaces: a
teacher assigns and assesses, a student attempts, the act of attempting (with or
without help) becomes immutable evidence, the engine weighs that evidence across
six dimensions, classifies any gap among ten types, fires a governed
intervention, watches the student reassess unaided, and updates mastery only on
fresh evidence — which the teacher then sees.

Both ends are two halves of one loop, so they are built together. The slice is
built to production depth on a deliberately narrow path — one board (a neutral
example state board), one grade (Class 10), two subjects (Mathematics, Physics)
— board-agnostic in the contract, proven narrow.

---

## 1. The loop

```
teacher assigns / assesses                                  (coursework B6, teacher surface)
  → student attempts            independent vs supported    (learning B7, student surface)
    → attempt event emitted     immutable, append-only      (event store, Ring 0)
      → evidence weighted       six mastery dimensions       (intelligence A3)
          Performance × Reliability × Independence
            × Difficulty × Recency × Consistency
        → gap classified        one of ten types             (intelligence A3)
            prerequisite · conceptual · procedural · application
            · retention · language · accuracy · speed
            · confidence · support-dependency
          → intervention fired   recommend, never auto-fire   (workflow A5, surfaces)
            → reassess unaided   the Independent rung          (learning B7)
              → mastery updates  only on FRESH evidence        (intelligence A3)
                → teacher sees it plain language, six-dim drawer (teacher surface)
```

Two correctness laws hold across the whole loop and are enforced in code, not
prose:

- **Independence is captured at the act, not inferred later.** Every attempt
  records whether help was used and at which rung of the assistance ladder. Only
  an unaided demonstration (the Independent rung) is evaluating; every other rung
  — including Check-my-work — is helping and is credited as supported.
- **A learner judgment is never confirmed from a single bad score.** Mastery is
  a multiplicative composite (a near-zero dimension caps the reading); a gap
  requires at least two corroborating signals or a reassessment before it is
  confirmed. One bad score is a prompt to reassess, never a verdict.

You can watch the entire cycle run, live and deterministic, in the browser at
`/loop` (see §9).

---

## 2. The contract surfaces (`@classess/contracts`, Slice 1 additions)

Five new contract surfaces were added under `contracts/src` as NEW files,
appended to `contracts/src/index.ts`. No Ring 0 event/evidence file was touched.
`tsc --noEmit` passes.

| Surface | Path | What it pins |
|---|---|---|
| Ontology | `contracts/src/ontology/` | Board/Grade/Subject/Unit/Chapter/Topic/Outcome/Competency node types, prerequisite `Edge` (hard/soft, `confirmed` flag + rationale), `CrossBoardEquivalence`, `OntologySnapshot`, and `SEED_ONTOLOGY` (Class 10 on a neutral example board, Mathematics + Physics, 13 topics, 13 can-do outcomes, 4 competencies, 9 prerequisite edges of which 8 are confirmed and 1 deliberately unconfirmed to model the steward-validation rule, 2 cross-board equivalences) with a stable `SEED_ONTOLOGY_IDS` map. |
| Evaluation | `contracts/src/evaluation/` | `EvaluationMode` (`post_submission` / `scanned_handwriting` / `preventive_before_submission`), `ResponseEvaluation` (answer_state correct/incomplete/misunderstood, rubric_score, confidence_band, needs_human_review, `never_penalize_handwriting: literal(true)`), `RubricCriterion`/`RubricScore`, and the `MarkingGate` human-final gate. `superRefine` forces a non-high band to flag review and blocks a consequential mark from being final without `human_confirmed` + `confirmed_by`. |
| Assistance | `contracts/src/assistance/` | Re-exports the single-source `AssistanceLevel` rung enum from `events`; adds the ordered `ASSISTANCE_LADDER` (Learn › Coach › Hint › Work-with-me › Check-my-work › Independent), `AssistanceMode`, and helpers `assistanceModeOf` / `isUnaidedDemonstration` / `assistanceRungIndex`. Only Independent is evaluating. |
| Recommendations | `contracts/src/recommendations/` | `Recommendation` (evidence_summary + evidence_refs lineage, confidence_band, owner role+ref, due_date, consequence_of_ignoring, why_am_i_seeing_this, suggested_action, `ladder_stage` recommend/prepare/execute_with_permission/safe_automatic, is_consequential) + `ApprovalDecision`. `superRefine` blocks any consequential recommendation from being `safe_automatic` and requires an adjustment description on `adjust`. |
| AI fabric | `contracts/src/ai/` | `Capability` descriptor (input/output schema refs, track 1/2, least-privilege `CapabilityScope`), `GenerateRequest`/`GenerateResult` with the `GenerateVerification` block (deterministic_checks, deterministic_checks_passed, second_model_agrees, confidence, gate_threshold, served). `superRefine` enforces INVARIANT 7 (served only when deterministic checks pass AND the second model agrees AND confidence ≥ threshold), `refused === !served`, and `provider_available`. `ModelTier` (frontier/mid/edge) + `RouterSelectionInput`/`RouterSelection`. |

**Naming-collision note for engine wiring.** The assistance module is exported
as a namespace (`export * as assistance`) to avoid duplicate flat exports of the
existing `AssistanceLevel`/`ASSISTANCE_LEVEL_DOCS`. The evaluation `EvaluationMode`
and the recommendations `LadderStage` use the spec's underscore spelling
(`post_submission`, `execute_with_permission`) and map one-to-one onto the
hyphen-cased event-layer `ScoreMode` and `PermissionRung` — this is the
workflow-runtime spelling versus the wire spelling; the engine modules carry the
mapping (see workflow `models.py` and coursework `contracts.py`).

---

## 3. Spine modules (Ring 1 core engines)

### 3.1 Intelligence — `spine/intelligence` (A3) — CORE

The evidence → mastery → gap projection engine. It computes derived learner
state by **replaying** the immutable event log; it never authors mastery
directly. Pure and deterministic — the same events always yield the same
reading, which is what lets a better model re-score every past learner.

- **Owns:** the six-dimension mastery model, the ten gap-type rules, evidence
  weighting, and the per-learner / cohort projections.
- **Exposes (Python `app/`):** `mastery.py` (six dimensions each in `[0,1]`,
  multiplicative composite `∏ dimension^weight`, guarded display bands and
  plain-language strings — never the formula or a raw number to a learner),
  `gaps.py` (all ten gap types as distinct rules; `MIN_SIGNALS_TO_CONFIRM = 2`),
  `evidence.py` (`EvidenceItem` back-referencing its source `event_id`, recency
  half-life weighting, mode/assistance/confidence weighting, `collect_evidence`
  replay, `has_fresh_evidence` freshness guard), `profile.py` / `graph.py` (the
  idempotent learner and cohort projections), `models.py` (pydantic mirrors of
  `contracts/src/events/*` and `contracts/src/ontology/*`; `PrerequisiteGraph`
  with `trusted_only` = confirmed edges).
- **Consumes:** the event/evidence + ontology contracts (read-only). PII-free —
  opaque `canonical_uuid` + topic ids only. Egress is gateway-only; degrades to
  `InMemoryEventSource` when no provider is configured.
- **Guarantees in code & tests:** independent vs supported changes the reading;
  a single bad score never confirms a gap; reassessment lifts mastery and clears
  the gap; an unconfirmed proposed prerequisite edge never routes; rebuilds are
  idempotent.

### 3.2 AI fabric — `spine/ai-fabric` (A4)

The model router and the generate-and-verify substrate. Deterministic-first: the
router, verifier, gate, orchestrator, and observability run on the standard
library alone — no live key is required for the deterministic paths or the tests.

- **`router.py`** — maps a `task_class` to a tier (frontier for hard/rare
  reasoning, mid for volume, edge SLM for the high-frequency ocean) via an
  auditable table plus a difficulty/latency fallback. `Track1Config` (external
  LLM, enabled) and `Track2Config` (proprietary/edge, reserved, disabled) are
  distinct frozen dataclasses with distinct env names and owners; `resolve()`
  never crosses tracks (INVARIANT 11). Keys are read by env var NAME; absence
  returns a clearly-marked unavailable result that never fabricates content.
- **`verify.py`** — a real deterministic arithmetic/expression verifier on a safe
  AST evaluator (no `eval`, no names, no calls): numeric recompute, bounds, and
  unit consistency for math/physics, no LLM needed. `SecondModelChecker` is an
  interface; the default `AbstainingSecondModel` never agrees, keeping the gate
  closed when no provider is present. `ConfidenceGate.evaluate` serves content
  ONLY when deterministic checks pass AND the second model agrees AND confidence
  ≥ threshold (default 0.85); otherwise withheld with a human-review reason.
- **`capability_registry.py`** — governed least-privilege capabilities
  (`content.generate-practice-item`, `evaluate.response`, `explain.step`,
  `conversation.companion-turn`) with input/output schema refs, declared track,
  minimal scope, `requires_verification`, and a permission-ladder rung. Grading
  (`evaluate.response`) is marked consequential.
- **`orchestrator.py`** — the thin Vidya entrypoint: resolve capability → enforce
  least-privilege purpose match → enforce the permission ladder (consequential
  capabilities return `requires_approval` unless an explicit human approval token
  is present) → route on the owning track → deterministic checks first → second-
  model cross-check → confidence gate → structured result with the verification
  block. No provider + no deterministic handle ⇒ a well-formed refusal, never
  fabrication. `DeterministicMathProvider` lets the no-LLM path produce
  verifiable content from payload claims.
- **`observability.py`** — span interface for cost/latency/quality; `NullTraceSink`
  no-ops without a backend, `BufferingTraceSink` for tests.

### 3.3 Workflow — `spine/workflow` (A5)

The seven-step proactive loop and the permission-ladder runtime that every
module's proactive behaviour runs on.

```
observe(events) → interpret(signals) → recommend()
    → approve() → execute() → outcome() → learn()
```

- **`loop.py`** — the seven composable steps. `observe` refuses PII keys
  (INV 1/2); `interpret` runs pluggable interpreters and drops single-evidence
  learner judgments unless corroborated (CORE); `recommend` dispatches signals to
  builders producing full-provenance `Recommendation`s; `approve` opens PENDING
  and records the human decision (never self-approves); `execute` is the
  permission gate returning an `ExecutionResult` clearance, never a side effect;
  `outcome`/`learn` produce an advisory `LearningNote` and never silently re-rung.
  `WorkflowCycle.run()` composes steps 1–3; approve/execute are driven explicitly
  so the human gate is never bypassed.
- **`permission.py`** — `classify_action` returns a `LadderDecision` (a decision
  object, never an act). Any effect that sends/submits/publishes/deletes/charges/
  grades is consequential, pinned to `execute_with_permission`, can never be
  `safe_automatic`, `may_autofire` always False. Non-consequential actions are
  `safe_automatic` only on an explicit, non-external allow-list; everything else
  fails closed to `recommend`.
- **`recommendations.py` / `approvals.py`** — recommendation builders that derive
  the ladder stage from the action (never caller-supplied) and validate the ten
  gap types; an append-only `ApprovalLedger` (pending → approved/adjusted/declined,
  terminal decisions never overwritten).

### 3.4 Module table

| Module | Owns | Exposes | Consumes |
|---|---|---|---|
| intelligence (A3) | derived learner state | mastery, gaps, evidence, profile/graph | events + ontology contracts |
| ai-fabric (A4) | routing + generate-and-verify | router, verify, registry, orchestrator | AI contracts; LLM provider by name |
| workflow (A5) | proactive loop + permission ladder | loop, permission, recommendations, approvals | recommendation contract; events |

---

## 4. Capability modules (Ring 1 features)

### 4.1 Coursework & assessment — `modules/coursework` (B6) — CORE evaluation

- **`assignments.py`** — ontology-mapped assignments / quick-checks / projects;
  AI-generated items must carry a passing verification block.
- **`papers.py`** — blueprint-driven (topic × difficulty band × cognitive level)
  multi-set paper generation that routes every item through the ai-fabric
  generate-and-verify substrate (consumed by file path, never modified). Only
  gate-served items are included; an unfilled cell is recorded as withheld and
  flagged for human review, never served unverified.
- **`evaluation.py`** — the three-mode engine (`post_submission`,
  `scanned_handwriting`, `preventive_before_submission`) producing per-response
  answer_state + rubric_score + confidence_band plus a submission-level
  `MarkingGate`. Consequential marks are human-final via `confirm_mark` (HIGH
  band = provisional-auto, MIDDLE/LOW = forced review). Poor scan/handwriting only
  flags `needs_human_review` and lowers confidence — it never reduces a mark.
- **`rubric.py`** — a five-rubric library with deterministic, breakdown-preserving
  scoring. **`originality.py`** — a similarity interface with a deterministic
  shingle/Jaccard fallback that RECOMMENDS to a human, never accuses.
- **`events.py`** — builds and emits `assignment.created` / `submission.created`
  / `score.recorded` / `attempt.recorded` on the exact contract shapes with the
  independent-vs-supported keystone flag, stamping `consent_ref` + `purpose`,
  opaque `canonical_uuid` only; degrades to returning the event object when no
  store is wired.
- **Design flag:** in the objective path a deterministically-correct answer with
  no live second model lands at MIDDLE + needs_review (not HIGH) — the engine
  never stands fully alone without the cross-check. Supply a second model to
  reach HIGH / provisional-auto.

### 4.2 Learning — `modules/learning` (B7)

Six capability files plus an engine bridge. Produces RECOMMENDATIONS and EVIDENCE
only; it never grades or sends.

- **`learn.py`** — the pose → struggle → reveal state machine
  (POSED/STRUGGLING/REVEALED/RESOLVED). A reveal/scaffold is refused
  (`StruggleNotGenuineError`) until a genuine attempt (minimum engaged time, never
  zero, or a submitted try) — the anti-explain-first guard. Whether help was used
  sets the keystone flag: help ⇒ supported at the rung consumed; clean unaided
  solve ⇒ the Independent rung ⇒ independent.
- **`ladder.py`** — the assistance ladder ported from the contract: fades support
  one rung at a time as mastery rises, steps back up on a fresh struggle, gates
  Independent on an independence floor, always declares helping vs evaluating.
- **`practice.py`** — adaptive, mistake-based next-item selection; each of the ten
  gap types maps to a distinct response (not generic more-questions); difficulty
  just beyond independent ability; no completion-tick field anywhere.
- **`revision.py`** — spaced retrieval against the forgetting curve
  `R = exp(-t/S)`; stability grows with each spaced success and resets on a failed
  recall; due when retention hits the target. (`INITIAL_STABILITY_DAYS = 7.0` so a
  single fresh independent success is not immediately flagged.)
- **`readiness.py`** — exam-readiness forecast from mastery + coverage, leaning on
  Independence (an exam is unaided), discounting revision-due and confirmed-gap
  topics; returns a plain-language verdict, never a raw percentage.
- **`_engine.py`** — a thin read-only pass-through to the intelligence engine
  (spine A3); never modifies it.

### 4.3 Content & resources — `modules/content` (B3)

Standard-library-only, import-safe; wires to the ai-fabric spine without
modifying it.

- **`repository.py`** — content metadata keyed to opaque ontology topic ids.
  Immutable `ContentVersion` history (never rewritten); approval lifecycle
  DRAFT → IN_REVIEW → APPROVED/REJECTED/RETIRED with an allowed-transition table;
  `LicenceMetadata` provenance. `is_servable` is true only for an APPROVED record
  with a live, verified version; `transition()` refuses to make an unverified
  version live. Semantic search behind one interface: `PgVectorSearchIndex`
  (production, reports unavailable until a DB handle is wired) degrading to
  `InMemorySemanticSearchIndex`; `search(only_servable=True)` keeps drafts out of
  learner results by construction.
- **`generate.py`** — builds an ai-fabric intent and delegates to the spine
  orchestrator. Only content whose `verification.served` is true is returned;
  withheld results are refusals carrying the reason. `generate_into_repository`
  files a DRAFT only (the permission ladder — agents prepare, humans approve).
- **`ingest.py`** — OCR / transcription / document-understanding protocols with
  `Null*` degraders that report unavailable rather than inventing text; produces
  UNVERIFIED DRAFT metadata only.
- **`verification_surface.py`** — a confidence-banded human review queue
  (GREEN/AMBER/RED as triage only, never a gate); an explicit human
  `ReviewDecision(APPROVE)` is the ladder act that promotes a record.

---

## 5. The Teacher and Student surfaces — `surfaces/web`

Both ends of the loop on the v4 design system, running and visible.

- **`lib/engine.ts`** — a faithful TypeScript port of the spine intelligence
  engine (`evidence.py`, `mastery.py`, `gaps.py`): the six dimensions with the
  multiplicative composite and plain-language bands, all ten gap rules, bound to
  `@classess/contracts` types and the ontology seed. Verified against the Python
  rules by transpiling and running standalone (every gap fires; a single bad score
  never confirms; near-zero Independence caps the composite below the independent
  band).
- **`lib/loopData.ts`** — the Class 10-B roster (Student A..H, opaque refs) and
  seed attempt events on the real Mathematics + Physics seed ontology, each
  student authored to tell one clear gap story.

**Teacher end**
- `/teacher` — the day view with a live attention list.
- `/teacher/assign` — blueprint-lite assignment with a Prepare → Approve gate that
  never auto-sends.
- `/teacher/evaluate` — a confidence-banded, human-final review table.
- `/teacher/students` — plain-language mastery with the six-dimension reasoning
  drawer and gap chips.

**Student end**
- `/student` — the today view.
- `/student/learn` — pose → struggle → reveal with the fading assistance ladder
  and a helping-vs-evaluating banner.
- `/student/practice` — adaptive, mistake-based, with a live read.
- `/student/progress` — the queryable knowledge profile with the ignite. The
  composite is used only as a sort key here, never displayed.

Learner-facing surfaces never render a raw score, the composite, or the formula —
only `you can do this independently` / `you can do this with guidance` /
`revision is due`. The rail is role-shaped via a shared `RoleContext`; Vidya stays
docked on every destination via `SurfaceShell`. Every new page ships empty,
loading, and error states.

---

## 6. Generate-and-verify and the confidence gate (INVARIANT 7)

No generated content is served unverified. The substrate lives in
`spine/ai-fabric/app/verify.py` and is contract-shaped by
`contracts/src/ai/index.ts`. A `GenerateResult` is served ONLY when all three
hold:

1. **deterministic checks pass** — symbolic/numeric recompute, bounds, and unit
   consistency for math/physics on a safe AST evaluator (no `eval`);
2. **the second model agrees** — a `SecondModelChecker`; the default abstaining
   model never agrees, so the gate stays closed with no provider;
3. **confidence ≥ the gate threshold** (default 0.85).

Otherwise the content is withheld with a human-review reason; `refused === !served`.
Coursework paper generation and content generation both consume this substrate;
a withheld item is recorded and flagged, never quietly dropped or served.

---

## 7. The permission ladder and human-final marking (INVARIANT 8)

```
Recommend → Prepare → Execute-with-permission → Safe-automatic
```

Anything that sends, submits, publishes, deletes, charges, or **grades** requires
explicit human approval; agents hold no credentials. `spine/workflow/permission.py`
pins every consequential action to `execute_with_permission` and forbids
`safe_automatic` (the contract `superRefine` enforces the same). `execute()`
returns a clearance, never a side effect — the actual act is delegated to a
governed capability behind the gateway.

Marking is human-final. The coursework `MarkingGate` makes a HIGH-band objective
mark a provisional-auto and forces MIDDLE/LOW to human review; a consequential
mark cannot be final without `human_confirmed` + `confirmed_by`. Poor handwriting
or a bad scan only flags review and lowers confidence — it never reduces a mark
(`never_penalize_handwriting`). On the surfaces, `/teacher/assign` and
`/teacher/evaluate` carry the Prepare → Approve / Approve · Adjust · Decline
controls and never auto-fire.

---

## 8. Environment variables (names only — never a value)

All secrets are environment-only and follow `clss.<app>.<env>.<purpose>`. None is
hardcoded; absence degrades gracefully behind a clear interface.

| Module | Env var names |
|---|---|
| ai-fabric | `clss.aifabric.dev.track1_router_url`, `clss.aifabric.dev.track1_provider_key`, `clss.aifabric.dev.track2_endpoint_url`, `clss.aifabric.dev.track2_endpoint_key`, `clss.aifabric.dev.tracing_url`, `clss.aifabric.dev.tracing_key` |
| intelligence | `clss.intelligence.dev.database_url`, `clss.intelligence.dev.gateway_url`, `clss.intelligence.dev.crosscheck_model_key` |
| workflow | `clss.workflow.dev.gateway_base_url`, `clss.workflow.dev.event_store_url`, `clss.workflow.dev.jwt_public_key`, `clss.workflow.dev.ai_fabric_route` |
| coursework | `clss.coursework.dev.event_store_url`, `clss.coursework.dev.gateway_url`, `clss.coursework.dev.gateway_token`, `clss.coursework.dev.ai_fabric_url`, `clss.coursework.dev.ocr_provider_key`, `clss.coursework.dev.originality_provider_key` |
| learning | `clss.learning.dev.gateway_url`, `clss.learning.dev.event_sink_url`, `clss.learning.dev.database_url`, `clss.learning.dev.crosscheck_model_key` |
| content | `clss.content.dev.pgvector_dsn`, `clss.content.dev.embedding_provider_key`, `clss.content.dev.ocr_provider_key`, `clss.content.dev.transcription_provider_key`, `clss.content.dev.doc_understanding_key` |
| web surface | `NEXT_PUBLIC_CLSS_WEB_PROD_GATEWAY_URL`, `CLSS_WEB_PROD_GATEWAY_TOKEN` |

The generation LLM key is owned and named by the ai-fabric router
(`clss.aifabric.dev.track1_provider_key`); the content and coursework modules
hold no key of their own and reference it through the gateway.

---

## 9. Running it

> Do not run installers or builds inside a single lane during the parallel build;
> the orchestrator installs and builds centrally. The steps below are what the
> central setup enables.

### 9.1 The surfaces (the visible loop)

```bash
# from surfaces/web, after the central npm install
npm run dev          # next dev — serves all Slice 1 routes
```

Then open `/loop` — the full cycle runs in-browser through `lib/engine.ts` over
real attempt events: assign → attempt (independent/supported toggle) → event
emitted → live six-dimension mastery + gap update → intervention with evidence /
confidence / owner / consequence and Approve · Adjust · Decline → reassess unaided
→ mastery updates → teacher reflection, with the ignite on a genuine independent
mastery moment. Engine determinism is anchored to a fixed `SCENARIO_NOW` so reads
are stable regardless of wall clock. All twelve routes return 200; `tsc --noEmit`
passes.

A build-config note inside the web directory: `surfaces/web/next.config.mjs` adds
a webpack `resolve.extensionAlias` (`.js → .ts/.tsx`) so Next's webpack resolves
the NodeNext-style `.js` specifiers in the contracts source. The contracts `dist/`
is pre-Slice-1 and stale, so the seed is resolved from source; no package rebuild
is needed.

### 9.2 The Python packages (tests)

Each package degrades to offline, deterministic behaviour with no provider. The
suites are written in standard pytest form. Because pydantic / pytest are not
installed in the current environment and installs are forbidden, the suites were
verified by clean byte-compile plus stdlib smoke harnesses; to run them once the
deps are present:

```bash
# spine engines
pip install -r spine/intelligence/requirements.txt && pytest spine/intelligence
pip install -r spine/ai-fabric/requirements.txt    && python -m pytest spine/ai-fabric
pip install -r spine/workflow/requirements.txt      && python -m pytest spine/workflow/tests -q

# capability modules
pip install -r modules/coursework/requirements.txt && python -m pytest modules/coursework
pip install -r modules/learning/requirements.txt    && python -m pytest modules/learning
python -m pytest modules/content   # standard-library-only
```

All suites are offline and need no live provider; the engine-integration tests in
`modules/learning` skip cleanly when the spine engine or pydantic is absent.

---

## 10. What this slice proves, and what it defers

It proves the loop end to end on real (in-browser) evidence: independent vs
supported genuinely changes the mastery reading; one bad score never confirms a
gap; a reassessment lifts mastery and clears the gap; an intervention is
recommended with full provenance and never auto-fires; nothing AI-generated is
served unless the confidence gate passes; marking is human-final.

It defers — behind named env vars, with no re-architecture — the live LLM
provider (Track 1, through the gateway), the Supabase event store and pgvector,
OCR / transcription, and the second-model cross-check that would let the objective
path reach HIGH / provisional-auto. See `docs/SLICE1-STATUS.md` for the
Checkpoint 1 status and the path to live provisioning.

The slice is proven narrow on purpose — one example board, Class 10, Mathematics
and Physics — board-agnostic in the contract (the board is a labelled node, never
an enum), ready to widen without changing shape.
