# Testing & CI

Testing is built in across the stack, not bolted on. Every module ships with its
own suite, and a single gate runs them all.

## One command

```bash
npm run ci          # the full gate: typecheck → vitest → pytest → web build
```

Individual layers:

```bash
npm run typecheck   # tsc --noEmit across contracts, design-system, web
npm test            # vitest (all three TS projects)
npm run test:py     # pytest across all six Python modules
npm run test:watch  # vitest in watch mode
```

## What is covered

### TypeScript (vitest — `vitest.workspace.ts`)
- **contracts** — the ten gap types are exactly ten; the seed ontology validates
  against the `OntologySnapshot` schema; every prerequisite edge and outcome
  references a real topic with no self-loops.
- **design-system** — the `cx` class joiner; `SpotlightCard` renders the `.card`
  + `.c-spot` contract classes (the signature hover); components render children.
- **web** — `lib/engine.ts` (the in-browser mastery/gap port) is tested for
  **parity with `spine/intelligence`**: independent vs support-dependent
  separation, no confident band from a single observation, strong-but-stale
  evidence reading "revision is due" (the latent-band rule), the plain-language
  layer never leaking a number or formula, and a gap never confirmed from one
  bad score.
- **web (voice)** — `lib/__tests__/voice.test.ts` covers the Vidya voice client's
  degraded path with no network: a 503 from the token route resolves to a calm
  `unavailable` (never a thrown error), a transient failure resolves to `error`
  with a retry, a successful mint moves the session to `listening` and holds only
  the opaque ephemeral token, token expiry is enforced, the subscriber lifecycle
  and an illegal-transition guard behave, and a fetch-stub exercises both the 503
  and reject paths. The browser never reads the raw key — only the env-var NAME is
  referenced. 9 voice tests; the web project is 16/16 passing.
- **web (parent surface, Slice 3)** — `lib/__tests__/parentData.test.ts` covers
  the Parent surface's consent-and-plain-language guarantees with no network:
  child-switch resolution (`findChild` / `resolveChildId` / `selectChildData`),
  **consent gating yields no data** (an unconsented or unknown child returns null
  so behavioural data cannot leak through the UI), three calm briefings per
  consented child, the plain-language scrub (no raw numbers, n/n scores,
  percentages, "marks", emoji, or exclamation marks), non-alarming tag tones, and
  proof-artifact integrity. 11 tests; with them the full web vitest suite is 27/27
  passing.

### Python (pytest — `scripts/test-python.sh`)
Each engine and module owns an isolated `app` package and `tests/` suite:
- `spine/intelligence` — the six mastery dimensions, the ten-gap classifier, the
  recency/latent-band revision rule, profile/graph rebuild from events.
- `spine/ai-fabric` — the deterministic verifier, the confidence gate
  (served vs withheld), Track 1 / Track 2 separation, the orchestrator, and the
  Vidya voice adapter (see "Voice (Gemini Live)" below).
- `spine/workflow` — the permission ladder never auto-fires a consequential
  action; recommendations carry full provenance; approval transitions.
- `modules/coursework` — the three-mode evaluation engine, blueprint papers,
  rubric scoring, event emission.
- `modules/learning` — pose-struggle-reveal, adaptive practice, the assistance
  ladder, spaced retrieval, readiness.
- `modules/content` — generate-and-verify wiring, repository, ingest.
- `modules/institution` — the structure-ladder containment rules, policy
  inheritance with locked floors, denied-by-default tenant isolation, the
  all-problems blueprint validation gate, and append-only event shapes (44 tests,
  standard-library-only).
- `modules/scheduling` — the working-day calendar math, the timetable solver
  (hard breaches disqualify, `apply_change` refuses without an approver), the
  substitution ladder (never an unsupervised free period), pacing drift bands, and
  event emission (37 tests, dependency-free).
- `modules/learner-record` (Slice 3, B8) — the consent + purpose gate
  denied-by-default (wrong purpose / scope / audience denied, revoked / expired
  denied, parent in-audience allowed, `require()` raises `ConsentDenied`, no PII in
  the reason); the profile read denied without consent, plain language never
  leaking a number / formula, independent vs support-dependent foregrounded, every
  item links to evidence and carries permission controls, no score field; the
  portfolio requiring provenance, rejecting a raw score in a caption, gating the
  shared view, append-only curation; credentials never faked as verified without a
  key, verifiable / tamper- / expiry- / revoke-failing with a key, gated export,
  PII-free portable self-export with full lineage; events requiring provenance,
  rejecting a number, PII-asserted, degrading to an in-memory append-only sink; and
  config dotted-name / env-by-name / fully-degraded paths (50 tests, stdlib-only
  path).
- `modules/communication` (Slice 3, B9) — safeguarding always escalating a crisis
  to a qualified human, flagging + escalating harassment, treating directed
  self-harm as crisis, refusing any unmonitored channel, the on-device fallback
  never silencing a crisis, `worst()` picking the highest severity; the companion
  refusing dependence / exclusivity / manipulation (scripted and model-generated),
  escalating a crisis and never counselling it, always carrying a safeguard, and
  pointing back to people; parent partnership denying a cross-context read without
  consent (revoked / mismatched / expired denied), refusing surveillance even with
  consent, returning partnership / pride framing with no raw number / formula; the
  hub screening every message, admitting a flagged message with an escalation
  (never dropped), promoting a message into a human-owned tracked task, and
  consent-gating cross-context routing; translation preserving text, masking /
  restoring subject terms verbatim, and preserving code-switch spans; and the
  emitter degrading to an in-memory sink, carrying the safety verdict not the body,
  refusing an unscreened message, using the intervention purpose for an escalation,
  and appending immutably (48 tests, dependency-free).
- `modules/intelligence-views` (Slice 3, B11) — one-metric-one-definition enforced
  (redefinition refused, identical-def idempotent, unknown refused, two callers
  agree, ratios clamped, plain language present, no emoji / exclamation); every
  dashboard alert carrying the full explainability set (evidence summary + linked
  refs, confidence band, owner role + opaque ref, consequence,
  why-am-i-seeing-this, suggested action, ladder stage), never auto-firing and
  never `safe_automatic`, no alert from a single bad score or a strong cohort, the
  headline resolving via the semantic layer, deterministic, degraded reasons as
  names only; forecasts reproducible / bounded (strong on-track-or-ahead,
  support-dependent at-risk-or-behind, thin evidence low-confidence); the study
  quadrant placing effort x outcome deterministically into four differentiated
  responses, explainable and learner-scoped; target analytics comparing target vs
  trajectory with gap-to-target, full explainability, owner + due, sorted
  most-at-risk-first, rejecting an invalid target; and ask-anything answering
  exactly the semantic-layer number, consent-gated, refusing an unscreened question,
  escalating a flagged one, refusing (not inventing) an unknown metric, and never
  showing a learner a raw unsafe number while still giving learner-safe coverage
  (49 tests; the spine `intelligence` / `workflow` packages are consumed as source
  under private namespaces, no install or build).

### Python — Ring 2

Each Ring 2 module owns an isolated `app` package and `tests/` suite; run them by
`cd`-ing into the module (import names collide otherwise) with the repo venv at
`/Users/depl/Documents/classess-school/.venv`. Every suite passes offline with no
network and no DB.

- `spine/integration` (A6) — roster import reduces external person ids to an opaque,
  salted `source_key` and drops all PII at the seam (the `assert_no_pii` backstop
  catches PII field names regardless of separator style and exempts `name` only under
  an `account` parent for the xAPI outbound actor); xAPI / Caliper round-trip through
  the internal activity shape with an opaque actor; connector-health states
  (UNKNOWN / UNCONFIGURED / HEALTHY / DEGRADED / DOWN) with hysteresis so a single
  blip does not flap; QTI / OneRoster / SCORM / LTI / CASE parse and serialise; the
  activity relay refuses to build without a `consent_ref` or a resolved
  `canonical_uuid`; the MCP surface returns prepared (not executed) consequential
  tools; config reads env by NAME and degrades cleanly (six suites, stdlib-only;
  53 tests, verified green via a stdlib runner and runnable under `python -m pytest`
  once pytest is on the path).
- `spine/governance` (A7) — append + immutable-query roundtrip with no mutation
  surface and frozen records; break-glass requires a reason (`ReasonRequiredError`),
  writes an immutable privileged entry, is reviewable, four-eyes-capable, and
  TTL-bounded; the control centre reports Track 1 / Track 2 separately (never summed),
  rejects an unknown track, exposes confidence-gate stats, and `emergency_disable`
  genuinely halts a capability via `guard()`; consent is closed by default, opens for
  one purpose, re-closes on revoke, honours KEEP / EXPIRE / LEGAL-HOLD, and lineage
  refuses any insight without a consent ref or sources; child-safety refuses an
  unmonitored channel, flags / blocks moderation, escalates a crisis to a human with
  a privileged audit entry, lets a crisis override softer verdicts, and abstains
  rather than asserting safe; tenancy is default-deny / read-down only across
  group / franchise / programme / network; all modules import-safe with settings
  defaulting to None and no hardcoded secret value in source (seven suites, 49 tests,
  stdlib-only; runnable via `python -m pytest spine/governance`).
- `spine/feature-store` (A3, Ring 2) — the registry is the single source of every
  feature and the feature vector is deterministic and order-independent, each value
  carrying its `name@version` definition key and source event ids; point-in-time
  correctness is leak-free (`events_asof` excludes the future, a past vector does not
  mutate when a future event is appended, observation count grows monotonically over
  asof); predictions are reproducible (predict-from-vector equals predict-from-events),
  carry full lineage (features + event ids + model / registry version), keep thin
  evidence low-confidence, and read supported-only as not exam-ready; backfill is
  deterministic and idempotent under shuffled input via a SHA-256 signature
  (four suites, 17 tests; consumes `spine/intelligence` through the audited interop
  seam — requires the sibling engine and the engine's deps to be present).
- `modules/ontology-ingestion` (A2) — ingestion maps source curriculum onto the typed
  ontology tables under correct parents with nodes always drafts, the null provider
  never inventing output, the confidence gate flagging low-confidence nodes, the SAME
  pipeline ingesting any board, and deterministic idempotent ids; proposed
  prerequisite edges start UNCONFIRMED and `confirm`/`reject` require a human steward
  ref (self-edge / unknown-topic refused, no PII on edges); cross-board equivalence is
  symmetric with equal confidence both ways, board-agnostic, deduped regardless of
  order, confidence-gated, and not auto-trusted; offline embedders are deterministic
  and L2-normalised with Track 1 / Track 2 lanes separate; the emitter degrades to an
  append-only in-memory sink (`edge_confirmed` refuses without a steward ref); the
  Python seed mirrors the contract counts and referential integrity (six suites,
  40 tests, stdlib-only path; `python -m pytest`).
- `modules/teacher-growth` (B10) — the four interaction metrics computed
  deterministically from opaque speaker refs; coaching signals refuse to be
  constructed public and widen audience only with the teacher's own consent ref, and
  `refuse_punitive_ranking` / `employment_decision_guard` are callable hard errors;
  the quality-review state machine has the teacher reflect first, requires findings to
  link evidence, always refuses `auto_finalise`, and requires the same human reviewer
  ref to sign off; the continuity note carries opaque refs only and a reflection
  travels only with the outgoing teacher's consent ref; events force coaching signals
  private + teacher_first, require a human ref for sign-off, and append immutably;
  config is env-name-only on both loader paths (six suites, 46 tests; `python -m pytest`).

### TypeScript — Ring 2 web surfaces (vitest)
- **web (Ring 2)** — `lib/__tests__/ring2Data.test.ts` covers the four Ring 2
  surfaces with no network: connector health + human-gating (a connector that writes
  data out is awaiting approval and never auto-fires), Track 1 / Track 2 separation
  and confidence-gate pass/withhold totals, the growth surface showing one insight at
  a time in a no-judgement tone with no score or ranking, and the network
  group → region → campus rollup surfacing only flagged nodes (manage-by-exception).
  17 tests; the full web vitest project passes 48/48.

## Voice (Gemini Live)

The Vidya speech-to-speech adapter (`spine/ai-fabric/app/voice.py`) ships 19 tests
inside the ai-fabric suite (60 tests total), all offline — the provider seams are
injected as in-process fakes via the `LiveTokenMinter` / `LiveAudioModel`
Protocols, so no network or live key is touched. The degraded-path coverage is the
core of the suite:

- with the SDK seam absent OR the key unset, both `mint_browser_session()` and
  `respond_speech_to_speech()` return `provider_available=False` with no token and
  no audio — never fabricating;
- the raw key is never present in any result object and a provider token equal to
  the raw key is rejected (defence in depth — an unavailable session result that
  carries a token raises);
- the server-side turn is served ONLY when the deterministic checks pass, the
  second model agrees, and confidence clears the gate; with the default abstaining
  second model the gate stays closed and the turn is refused with a reason;
- the capability sits on the RECOMMEND rung and a consequential follow-on requires
  an `approval_token` before audio is emitted.

The config loader is tested on both paths: pydantic-settings when present and the
standard-library fallback (same `CLSS_AIFABRIC_DEV_` prefix and field) when absent,
so the package stays import-safe with no third-party dependency. The web side of
the same capability is covered by `surfaces/web/lib/__tests__/voice.test.ts`
(see above).

## Engine parity (a deliberate invariant)

The mastery/gap logic exists twice — `spine/intelligence/app/mastery.py` (the
production core) and `surfaces/web/lib/engine.ts` (the in-browser loop). They
must agree. The web parity test encodes the same scenarios as the Python suite;
when one engine's rule changes, the other's test fails until it is brought back
in line. The recency → "revision is due" latent-band fix was applied to both.

## CI

`.github/workflows/ci.yml` runs two parallel jobs on every push and PR:
- **typescript** — `npm ci`, typecheck, vitest, and a full `next build` of the
  web surface (which catches RSC / route-boundary errors).
- **python** — installs `requirements-dev.txt` and runs `scripts/test-python.sh`.

## Local Python toolchain

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
```
