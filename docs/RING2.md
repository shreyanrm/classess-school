# Classess School — Ring 2: the standards bridge, ontology, growth, governance, the feature store, Track 2, and the Ring 2 surfaces

This is the build document for Ring 2. Where Ring 0 laid the secure base and Ring 1
cut the learning loop and the institutional, relationship, and composition layers
in three slices, Ring 2 builds the **connective and governing tissue** that lets the
platform live on top of systems schools already run, keep its curriculum graph
alive, grow its teachers, govern its most powerful surfaces, and turn the immutable
event log into reproducible features and forecasts.

Ring 2 binds to the same frozen `@classess/contracts` boundary and the same twelve
invariants. It adds two spine capabilities that govern and connect (`spine/integration`,
`spine/governance`), one derived spine store (`spine/feature-store`), the proprietary
Track 2 slot in `spine/ai-fabric`, two capability modules (`modules/ontology-ingestion`,
`modules/teacher-growth`), and four web surfaces under `surfaces/web/app`.

Everything degrades gracefully with no live keys, no DB, and no network. Every
module names its env vars by NAME only, holds no secret value, and ships a passing
suite that runs offline.

---

## 1. The two-track separation (Invariant 11), made concrete in Ring 2

Two tracks of model intelligence stay structurally separate in config and in
ownership — they are never summed, never conflated, and never share a key:

- **Track 1** — external / open-standard intelligence. Hosted LLMs, open standards
  (LTI, OneRoster, xAPI, Caliper, QTI, SCORM, Clever, ClassLink, Ed-Fi, CASE),
  Track 1 embedding/forecast model slots.
- **Track 2** — proprietary / edge intelligence. The small/fast on-device-style
  SLM adapter in `spine/ai-fabric/app/track2.py`, the Track 2 connector slot in the
  integration bridge, the Track 2 embedding/forecast model slots, and a separate
  child-safety edge-model seam in governance.

Ring 2 enforces this in code, not just docs: the integration config splits the
Track 2 connector URL into its own field; the feature store keeps Track 1 / Track 2
forecast keys in separate config fields; ontology-ingestion keeps Track 1 / Track 2
embedding keys in separate env vars; the AI control centre's `track_view()` reports
the two tracks in separate buckets and rejects an unknown track; and the Track 2 SLM
adapter reads only Track 2's own named endpoint key/url and never borrows Track 1's.

---

## 2. The modules

### 2.1 `spine/integration` — A6, the FLUID two-way standards bridge

The connector framework and standards adapters that let the platform run as the
intelligence layer on top of an existing system, take it over, or simply exchange
data. It speaks the standards school systems already speak and maps everything into
the spine's opaque, board-agnostic ontology and canonical identity.

- **Owns:** the connector framework (`connector.py` base + `registry.py` set/health
  tracking); the identity + ontology seam (`mapping.py`); connector-health
  monitoring with hysteresis (`health.py`); the activity relay into the immutable
  event store (`events.py`); standards-neutral, PII-free internal shapes plus the
  PII backstop (`models.py`); and interface-complete adapters under `adapters/` for
  LTI 1.3, OneRoster 1.2, xAPI, Caliper, QTI 2.x/3.0, SCORM 1.2/2004/cmi5, Clever,
  ClassLink, Ed-Fi, CASE, and an MCP server surface.
- **Exposes:** per-standard parse/serialise adapters that turn external records into
  PII-free internal shapes and back; `source_key` minting (an opaque, salted
  one-way ref) and gateway-resolved `canonical_uuid`; connector-health states
  (UNKNOWN / UNCONFIGURED / HEALTHY / DEGRADED / DOWN) with hysteresis so a single
  blip does not flap a connector; prepared, approval-gated descriptors for
  consequential effects (grade passback, LRS/Caliper forward, deep-linking, MCP
  consequential tools).
- **Consumes:** the gateway (every outbound effect is a descriptor handed to a
  governed gateway capability — adapters hold no credentials); the identity vault
  via an injected resolver Protocol (to resolve `canonical_uuid`); the ontology via
  an injected resolver (to map outcomes / CASE frameworks); the immutable event
  store via the gateway.
- **Invariants in code:** PII is dropped at the seam — only the opaque salted
  `source_key` (`HMAC-SHA256(salt, standard:normalized_id)`) and, when identity is
  online, the random `canonical_uuid` ever cross a boundary. `assert_no_pii` is a
  hard backstop on every cross-boundary object and detects PII field names
  regardless of separator style (`givenName` == `given_name`). The xAPI outbound
  actor carries the opaque id in `account.name` (legitimate xAPI structure), so the
  backstop exempts a `name` token only when its parent key is `account`. The
  activity relay refuses to build without a `consent_ref` or a resolved
  `canonical_uuid`. Track 1 / Track 2 connector config is separated.

### 2.2 `spine/governance` — A7, governance and child-safety

The most powerful surfaces, the best governed. The spine's governance core:
immutable audit, break-glass, the AI control centre, consent / retention / lineage,
the child-safety subsystem, and tenant isolation. Deterministic-first and
dependency-free.

- **Owns:** `audit.py` (immutable append + query layer; no update/delete surface
  exists; in-memory and Postgres adapters over `platform.audit_log` with INSERT-only
  grants); `breakglass.py` (privileged access requires a non-empty reason, writes an
  immutable PRIVILEGED audit entry, is time-boxed, reviewable, four-eyes-capable);
  `control_centre.py` (model usage reporting, Track 1 / Track 2 separated view,
  confidence-gate stats, an emergency-disable kill switch that genuinely halts a
  capability via `guard()`); `consent.py` (the cross-context read gate, retention
  KEEP / EXPIRE / LEGAL-HOLD, and a lineage service that refuses any insight without
  a consent ref or a source); `child_safety.py` (moderation, crisis detection,
  escalation to qualified humans, no unmonitored channels — on every free-text
  surface); `tenancy.py` (deterministic isolation policy across group / franchise /
  programme / network, default deny, read-down only).
- **Exposes:** the audit `record`/`query` pair; break-glass `open`/`list_for_review`/
  `review`/`close`; the control-centre `track_view`/`confidence_gate_stats`/
  `emergency_disable`/`guard`; consent `is_satisfied`/`grant`/`revoke` and the
  `LineageService`; the child-safety `screen`/`escalate` surface; and the tenancy
  read-policy decision.
- **Consumes:** the platform audit migration (`audit.audit_log`); consent / retention
  records; injected Track 1 and Track 2 child-safety classifier seams (behind
  separate keys); an escalation webhook seam.
- **Invariants in code:** audit is immutable and has no mutation method to call;
  break-glass demands a reason and appends superseding records on review/close;
  the control centre never sums the two tracks and rejects an unknown one; consent
  is fail-closed and denied-by-default with lineage on every insight; child-safety
  refuses an unmonitored channel, treats a crisis as overriding softer verdicts,
  and the default deterministic classifier abstains rather than asserting safe;
  tenancy defaults to deny. No PII anywhere — identity is referenced only by opaque
  `canonical_uuid` / actor refs.

### 2.3 `spine/feature-store` — A3 (Ring 2), the feature store and prediction layer

The derived feature store and the prediction layer on top of it. It computes
derived, versioned features per learner and topic and forecasts trajectory,
exam-readiness, and risk. Like every derived store in the spine it is a
**projection built by replaying the immutable event log** — it never authors
features or predictions directly.

- **Owns:** `registry.py` (the feature definitions — one definition, named,
  versioned, self-describing, with a pure compute function over a point-in-time
  window; every value stamped with its `name@version` key); `features.py` (the
  point-in-time-correct feature store — a single `events_asof` leakage guard, the
  engine's mastery computed over exactly that window, each value carrying its source
  event ids); `prediction.py` (reproducible trajectory / exam-readiness / risk
  forecasts, each carrying its exact features, confidence band, source event ids,
  and model + registry versions, with a sample-size-first confidence gate and risk
  framed as a read behind the permission ladder); `backfill.py` (rebuild by
  replaying events, idempotent via a SHA-256 content signature, plus a leak-free
  point-in-time series for training sets).
- **Exposes:** the feature vector and learner snapshot for a (learner, topic) as of
  an instant; reproducible predictions with full lineage; deterministic, idempotent
  backfill and a point-in-time series.
- **Consumes:** the intelligence engine (`spine/intelligence`, the evidence →
  mastery → gap engine) through a single audited seam (`app/intelligence_interop.py`,
  which loads the sibling engine under the distinct top-level name
  `clss_intelligence_engine` to avoid the `app/app` collision). It does not
  reimplement mastery, gaps, or evidence weighting; it reads the engine's
  point-in-time output. The engine source is never modified. It also consumes the
  immutable event log it projects.
- **Invariants in code:** PII-free (opaque `canonical_uuid` + topic ids only);
  immutable events replayed, never authored; point-in-time correct (no future
  leakage, ever); Track 1 / Track 2 forecast slots separate; predictions are reads
  behind the permission ladder, not auto-fired actions; the confidence gate keeps
  thin evidence provisional; every prediction is explainable (evidence / confidence /
  lineage / why). **Dependency:** the engine must remain a sibling under `spine/`;
  the shim raises a clear named error if absent (a missing upstream is a defect,
  not a degraded mode).

### 2.4 `spine/ai-fabric/app/track2.py` — A4, the Track 2 proprietary / edge SLM adapter

The reserved Track 2 slot in the AI fabric, now filled with a proprietary / edge SLM
adapter kept separate from Track 1 in config and ownership, without changing any
existing router / verify / voice / registry behavior.

- **Owns:** `Track2Adapter` for the high-frequency edge tier (small / fast /
  on-device-style SLMs); two governed capabilities (`content.generate-hint` →
  edge-slm-hint, `classify.intent` → edge-slm-intent), each registered with
  `track=2`, `requires_verification=True`, on the RECOMMEND rung, with a
  least-privilege scope (single purpose code + minimal data scopes
  `ontology.skill` / `conversation.context`, no PII); `track2_config()` returning a
  `Track2Config` bound to the edge model and Track 2's own endpoint key/url env
  NAMES; `register_track2_capabilities(registry)`.
- **Exposes:** the two edge capabilities (whose task classes map to the EDGE tier in
  the existing router's auditable table, so the router selects edge for them), and
  the Track 2 config.
- **Consumes:** the existing `ConfidenceGate` from `verify.py` (deterministic checks
  → independent second-model agreement → threshold); the default registry to register
  the edge caps alongside Track 1; Track 2's named endpoint key/url, read only at
  call time.
- **Invariants in code:** secrets ENV-ONLY, read by NAME, default None, never
  hardcoded / returned / logged; the adapter holds no credentials and degrades
  gracefully (`provider_available=False`, `refused=True`, env-var names in the
  reason) when URL/key/seam are absent — never fabricating; Track 2 output runs
  behind the same confidence gate (with no live endpoint the second model abstains
  and the gate stays closed); edge caps on the RECOMMEND rung; Track 1 and Track 2
  never conflated. Existing files were untouched beyond `config.py` additions
  (`track2_endpoint_url` / `track2_endpoint_key` under the existing
  `CLSS_AIFABRIC_DEV_` prefix, on both the pydantic-settings and stdlib paths) and
  `__init__.py` / README docs; `router.py`, `verify.py`, `voice.py`,
  `capability_registry.py`, `orchestrator.py` are unchanged.

### 2.5 `modules/ontology-ingestion` — A2, curriculum ingestion and the prerequisite steward

The curriculum-and-ontology ingestion pipeline over the existing board-agnostic
ontology contract (`contracts/src/ontology`). It ingests curriculum from documents /
standards / publisher content into the typed ontology graph, proposes prerequisite
edges for human confirmation, and registers symmetric cross-board equivalences.

- **Owns:** `ingest.py` (ingests curriculum via a `DocumentUnderstanding` Protocol
  that degrades gracefully — `NullDocumentUnderstanding` never invents output;
  structured-source path; pending-extraction state — mapping each outline node onto
  its typed ontology table board → grade → subject → unit → chapter → topic →
  outcome → competency under its parent, with a confidence gate flagging
  `needs_review` and deterministic idempotent ids; nodes are always drafts);
  `steward.py` (the prerequisite-edge steward — PROPOSES edges that start
  `confirmed=False`; `trusted_edges()` returns only steward-confirmed edges;
  `confirm()`/`reject()` require an explicit opaque steward ref and the steward never
  self-confirms); `equivalence.py` (a symmetric, board-agnostic cross-board
  equivalence registry: A ≡ B implies B ≡ A with equal confidence; propose-then-
  confirm; confidence-gated lookups; boards are code labels with no special-casing);
  `embeddings.py` (the pgvector semantic-index interface — `Embedder` + `VectorIndex`
  Protocols — with deterministic offline fallbacks `HashingEmbedder` and exact
  `InMemoryVectorIndex`, Track 1 / Track 2 model lanes in separate env vars);
  `events.py` (emits `ontology.node_ingested` / `edge_proposed` / `edge_confirmed` /
  `equivalence_mapped` on the attributed append-only envelope; `edge_confirmed`
  refuses without a steward ref); `_ontology.py` (a faithful Python dataclass mirror
  of the TypeScript ontology types) and `seed.py` (a Python mirror of `seed.ts` with
  identical stable ids).
- **Exposes:** the ingest pipeline; the trusted-edge view; the equivalence registry;
  the semantic-index seam; the ontology event surface.
- **Consumes:** the board-agnostic ontology contract; the gateway-backed event sink;
  pgvector and a document-understanding provider (both behind named env vars; live
  provider paths raise `NotImplementedError` by design while no provider exists — the
  Protocols are the contracts and the deterministic offline paths are the supported
  paths).
- **Invariants in code:** nodes are always drafts; the SAME pipeline ingests any
  board (no board hard-coded); proposed edges and equivalences start UNCONFIRMED and
  need an explicit human steward ref to be trusted (permission ladder); the
  confidence gate flags low-confidence nodes; equivalence is symmetric and board-
  agnostic; no PII on any edge or in any event payload; ids are deterministic and
  idempotent.

### 2.6 `modules/teacher-growth` — B10, teacher growth

Private, growth-framed teacher development built on the same conventions as the
sibling capability modules. AI never decides employment and there is never a league
table.

- **Owns:** `interaction.py` (the four deterministic classroom-interaction metrics
  from a lesson's delivery / engagement utterance stream — talk ratio, questioning
  quality, equity of voice as 1−Gini participation evenness, and wait time — using
  opaque speaker refs only); `coaching.py` (turns those metrics into private,
  teacher-first `CoachingSignals` — one growth-framed signal per dimension with a
  reading, an optional next step, evidence, and a confidence band; signals refuse to
  be constructed public and the audience widens only with the teacher's own consent
  ref; two prohibitions are callable hard errors — `refuse_punitive_ranking` and
  `employment_decision_guard`); `quality_review.py` (a human-owned state machine
  draft → teacher_reflection → reviewer_review → awaiting_sign_off → closed where the
  teacher reflects first, findings must link evidence, `auto_finalise` always
  refuses, and sign-off requires the same human reviewer ref); `continuity.py` (the
  knowledge-transfer / handover note — curriculum position + generic pedagogy +
  opaque refs; a coaching reflection travels only with the outgoing teacher's consent
  ref); `events.py` (emits `coaching.signal_generated` forced private + teacher_first
  on the envelope, `quality.review_signed_off` requiring a human ref, and
  `continuity.handover_recorded`, degrading to a labelled in-memory sink).
- **Exposes:** the interaction metrics, the private coaching signals, the quality-
  review state machine, the continuity note, and the growth event surface.
- **Consumes:** the gateway-backed event sink (the live POST path is a
  `NotImplementedError` behind the documented interface, with the in-memory append-
  only sink as the supported degraded path — consistent with the sibling modules).
- **Invariants in code:** opaque refs only (no name/email fields anywhere);
  append-only emitter; consent gates a coaching signal entering a review or handover;
  no punitive auto-ranking is producible and review sign-off / employment decisions
  require an explicit human ref (human authority); secrets env-name-only.

### 2.7 The Ring 2 web surfaces — `surfaces/web`

Four surfaces on the v4 brand, with the rail wired to reach them and Vidya docked on
every page via `SurfaceShell`.

- **`app/admin/integrations/page.tsx`** — the Matrix connector hub (LTI, OneRoster,
  xAPI, QTI, SCORM, Clever, Ed-Fi, CASE, MCP) split into Track 1 (open standards) and
  Track 2 (platform / edge), each cell carrying a health Tag (Connected / Available /
  Needs a look / Sync failed / Awaiting approval) and last-sync. Enabling a connector
  that writes data out is human-gated with an explicit Approve and never auto-fires.
- **`app/admin/control-centre/page.tsx`** — model usage with a clear Track 1 vs
  Track 2 split, confidence-gate pass/withhold stats + pass-rate bars, an emergency-
  disable control (typed DISABLE confirmation, human authority, restore), and an
  append-only break-glass + lineage list.
- **`app/teacher/growth/page.tsx`** — private coaching (talk ratio, questioning,
  equity of voice, wait time), one insight at a time, growth not judgement, no score
  and no ranking, with a single small experiment to try.
- **`app/admin/network/page.tsx`** — group → region → campus rollups (mastery trend +
  open interventions) with a manage-by-exception section surfacing only flagged nodes
  and a collapsible tree.
- **Shared:** `lib/ring2Data.ts` holds all shared logic; page files export only a
  default. `Rail.tsx` now gives admin Network / Integrations / AI control centre and
  teacher Your growth. First-class states (empty / loading / error via the existing
  route-level boundaries, offline via the `SurfaceShell` banner, plus in-page empty
  states). v4 only — only existing design-system primitives and house icons, scoped
  CSS using v4 tokens, no shadows, sharp corners, one accent.
- **Consumes:** `@classess/design-system` and TYPES only from `@classess/contracts`;
  the live data path remains the gateway + event store (env names already centralised
  in `lib/runtime.ts`), with the mocks as the graceful-degradation fallback.

---

## 3. How to run

> Do not run installers or builds inside an individual module during the parallel
> build; the orchestrator installs and builds centrally. Secrets are environment-only
> — see `ops/ENV.md`. With nothing configured every module starts in a clearly-
> labelled degraded mode (in-memory sinks, abstaining classifiers, offline embedders,
> deterministic fallbacks) so the contracts are exercisable without live keys or DB.

### 3.1 The Python modules

Each module owns an isolated `app` package and `tests/` suite; test them in isolation
by `cd`-ing into the module so import names do not collide. The repo venv at
`/Users/depl/Documents/classess-school/.venv` carries pytest:

```bash
# from the repo root
for m in spine/integration spine/governance spine/feature-store \
         modules/ontology-ingestion modules/teacher-growth; do
  ( cd "$m" && /Users/depl/Documents/classess-school/.venv/bin/python -m pytest -q )
done
# Track 2 lives inside the ai-fabric suite:
( cd spine/ai-fabric && /Users/depl/Documents/classess-school/.venv/bin/python -m pytest -q )
```

`spine/feature-store` additionally requires its sibling `spine/intelligence` to be
present (it consumes the engine through `app/intelligence_interop.py`).

### 3.2 The web surfaces

The Ring 2 surfaces run inside the existing web home (see `docs/BUILD.md` §5.1):
`npm run dev` serves them and `tsc --noEmit` typechecks. The full web vitest project
passes including the 17 new Ring 2 tests in `lib/__tests__/ring2Data.test.ts`.

---

## 4. Environment variables (names only — never a value)

All names follow `clss.<app>.<env>.<purpose>`; the matching env var uppercases and
replaces dots with underscores (for example `clss.integration.dev.gateway_base_url`
→ `CLSS_INTEGRATION_DEV_GATEWAY_BASE_URL`). No value is hardcoded; none is a
`NEXT_PUBLIC_` secret.

### `spine/integration`
```
clss.integration.dev.gateway_base_url
clss.integration.dev.event_store_url
clss.integration.dev.identity_base_url
clss.integration.dev.ontology_base_url
clss.integration.dev.jwt_public_key
clss.integration.dev.source_key_salt
clss.integration.dev.lti_platform_issuer
clss.integration.dev.lti_jwks_url
clss.integration.dev.oneroster_base_url
clss.integration.dev.clever_base_url
clss.integration.dev.classlink_base_url
clss.integration.dev.edfi_base_url
clss.integration.dev.case_registry_url
clss.integration.dev.caliper_endpoint_url
clss.integration.dev.xapi_lrs_url
clss.integration.dev.track2_connector_url          # Track 2, separate
```

### `spine/governance`
```
clss.governance.dev.audit_database_url
clss.governance.dev.breakglass_database_url
clss.governance.dev.consent_database_url
clss.governance.dev.child_safety_classifier_url    # Track 1
clss.governance.dev.child_safety_classifier_key    # Track 1
clss.governance.dev.child_safety_edge_model_url    # Track 2, separate
clss.governance.dev.child_safety_edge_model_key    # Track 2, separate
clss.governance.dev.escalation_webhook_url
clss.governance.dev.escalation_webhook_key
```

### `spine/feature-store`
```
clss.feature-store.dev.database_url
clss.feature-store.dev.gateway_url
clss.feature-store.dev.feature_cache_url
clss.feature-store.dev.track1_forecast_model_key   # Track 1
clss.feature-store.dev.track2_forecast_model_key   # Track 2, separate
```

### `spine/ai-fabric` (Track 2 additions only)
```
CLSS_AIFABRIC_DEV_TRACK2_ENDPOINT_URL              # Track 2, separate
CLSS_AIFABRIC_DEV_TRACK2_ENDPOINT_KEY              # Track 2, separate
```

### `modules/ontology-ingestion`
```
clss.ontology.dev.gateway_url
clss.ontology.dev.event_sink_url
clss.ontology.dev.database_url
clss.ontology.dev.pgvector_url
clss.ontology.dev.doc_understanding_key
clss.ontology.dev.embeddings_track1_key            # Track 1
clss.ontology.dev.embeddings_track2_key            # Track 2, separate
```

### `modules/teacher-growth`
```
clss.teachergrowth.dev.gateway_url
clss.teachergrowth.dev.event_sink_url
clss.teachergrowth.dev.database_url
clss.teachergrowth.dev.workflow_url
```

### Ring 2 web surfaces
No new env vars; the live data path reuses the gateway / event-store names already
centralised in `surfaces/web/lib/runtime.ts`.

---

## 5. Notes on the build environment

Several Ring 2 Python modules are implemented in pure standard library
(dataclasses, `xml.etree`, `hmac`/`hashlib`, `csv`) rather than pydantic, so the
packages stay import-safe and the suites pass with zero third-party dependencies.
Where a module uses the established sibling pattern (config prefers pydantic-settings
and degrades to a stdlib dataclass loader with the identical prefix + fields), both
paths are exercised. Live provider paths (a Postgres audit sink, a real moderation /
crisis classifier, a real document-understanding provider, a pgvector index, a real
embedder, the gateway-backed event POST) raise a clear named error by design while no
provider exists — the Protocols are the contracts and the deterministic offline paths
are the supported paths, each naming the exact env var to wire. No installer or build
was run inside any module during the parallel build.
