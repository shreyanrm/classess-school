# Completion Wave 1 (W1)

Status record for the first completion wave. This document covers the autonomous
Vidya orchestrator and its tool/permission surface, the new domain modules
(attendance, planning, classroom, exam-ops, mocks, groups, misconception, dedup,
artifacts), the gateway hardening pass and module route registration, how the
pieces connect, how to run them, and the environment variable names each needs.

All product copy here follows the confidentiality rules: generic labels only, no
codenames, no real personal names, no real pricing, no emoji, no exclamation
marks. Secrets are named, never valued. Env-var keys follow
`clss.<app>.<env>.<purpose>`; no `NEXT_PUBLIC_` secret is ever introduced.

---

## 1. The autonomous Vidya orchestrator

Vidya is the autonomous assistant surface. It plans, calls tools through the
gateway, and proposes actions, but it never auto-fires anything consequential.

### Surfaces and entry points

- `surfaces/web/lib/vidya.ts` — the client/server orchestrator library. Holds
  the turn loop (intent -> tool selection -> generate-and-verify -> proposal),
  the tool registry binding, and the confidence gate. Server-side only for any
  secret-bearing path; no secret is exposed through `NEXT_PUBLIC_`.
- `surfaces/web/app/api/vidya` — the API route(s) that the web surface calls.
  Every outbound model or data call is routed through the gateway wall; the route
  itself holds no behavioral PII and forwards only opaque `canonical_uuid`.

### Tools

Vidya operates a set of typed tools. Each tool is a thin, declared capability:

- It has a fixed input schema (validated at the gateway wall before routing, see
  Section 3).
- It returns structured results, never free-form side effects.
- It is classified `consequential` or not. Consequential tools (anything that
  writes, schedules, exports, sends, or finalises) cannot auto-execute.

### Permission ladder

The orchestrator honours the permission ladder invariant end to end:

1. Vidya may READ and ANALYSE within consent scope without a human gate.
2. Vidya may PROPOSE a consequential action, producing a draft/proposal object.
3. A human must APPROVE before the consequential tool actually fires.
4. The approval, like all events, is immutable and append-only.

Generate-and-verify wraps every generative step: Vidya generates a candidate,
verifies it (structure + topic/coverage + child-safety), and a confidence gate
withholds low-confidence output for human review rather than serving it. Every
free-text surface in the loop passes the child-safety screen.

### Degrade-gracefully behaviour

With no live model key or DB, Vidya degrades: the orchestrator falls back to
offline/conservative paths, holds anything it cannot verify, and surfaces a plain
"needs review" state instead of inventing output. Required keys are named only
(see Section 6).

---

## 2. New domain modules

Each module is an import-safe Python package: no network, no DB, and no secret is
read at import time. Cross-context dependencies are injected (resolvers,
adapters, sinks) so each package runs offline and is unit-testable in isolation.

### 2.1 Attendance (`modules/attendance`)

Attendance intelligence. Five capture methods are all modelled as
ASSIST-then-confirm: each method yields a draft roll and only an explicit
`confirm_roll(confirmed_by=...)` finalises it. Nothing auto-fires.

- `app/capture.py` — draft capture across all methods; confidence gate routes
  low-confidence/unknown marks to review; PII-free marks (opaque
  `canonical_uuid` only).
- `app/risk.py` — advisory risk detection: `consecutive`, `chronic`, `pattern`
  findings, each with severity, opaque id, and `needs_human_review`.
- `app/reconciliation.py` — combines multi-method drafts; flags present-vs-absent
  conflicts for human review; never auto-resolves material disagreement.
- `app/staff.py` — draft staff attendance; a substitution request is built ONLY
  from a human-confirmed absence.
- `app/events.py` — immutable, append-only, PII-guarded event builders, including
  `substitution_needed_event`, which is the scheduling trigger (substitution flows
  to scheduling via an event, not a direct call).
- `app/safety.py` — child-safety + PII screen on every free-text surface; offline
  and conservative; the gateway holds the authoritative classifier.

### 2.2 Planning (`modules/planning`)

Teacher planning and instruction design.

- `app/plans.py` — annual -> unit -> weekly -> daily hierarchy; every leaf is
  anchored to an ontology learning outcome (`OutcomeRef`). `PlanGenerator.adapt()`
  adapts the next plan to prior performance: incomplete items roll forward
  (prioritised), below-threshold outcomes gain reinforcement, above-threshold
  outcomes are trimmed/de-prioritised. The base plan is never mutated.
- `app/differentiation.py` — maps an opaque 0..1 mastery estimate to one of four
  readiness bands (emerging/developing/secure/extending) and assigns a
  band-appropriate task; unmatched learners are flagged, never mis-assigned.
- `app/diary.py` — teacher diary: planned vs delivered per item; status
  auto-updates (planned/partial/delivered); exposes a planned-vs-delivered summary
  and undelivered gaps.
- `app/pacing_link.py` — advisory pacing signals (behind/on_track/ahead) routed to
  an injected scheduling intake adapter; advisory only, confidence-gated.
- `app/events.py` — immutable, append-only planning events; runtime PII guard;
  corrections are successor events (no update/delete).

### 2.3 Classroom (`modules/classroom`)

Live-class delivery engine. The canonical engines live in `board_state.py`,
`live_session.py`, `poll_engine.py` and are bound to their public names through
`app/__init__.py`. Consumers import via the `app` package, not raw file paths.

- `app/events.py` — immutable append-only delivery/engagement/grasp events; opaque
  id only; PII-key refusal; gateway-bound envelope intents.
- `app/board_state.py` — infinite-canvas board (pages, strokes, objects); on-device
  vision hint that ASSISTS only, is confidence-gated (0.70), never grades from a
  face, never stores raw image bytes.
- `app/live_session.py` — join/presence; breakout rooms restricted to present
  participants; session close on the permission ladder (`request_close` stages,
  `approve_close` requires explicit human approval, never auto-fires);
  consent-gated roster export.
- `app/poll_engine.py` — single-choice and quiz polls; real-time tally; idempotent
  one-vote-per-subject; child-safety on every free-text prompt/option; quiz result
  is learning evidence, not a sanction.
- `app/device_free_check.py` — opaque card-scan presence check; idempotent; invalid
  scans non-punitive.
- `app/attention.py` — engagement signals that are structurally assistive,
  non-punitive, and non-identity-graded; confidence-gated (0.60) to UNCERTAIN;
  vision input never from a face.

### 2.4 Coursework extensions (`modules/coursework`)

Exam operations, mock generation, and group composition. These EXTEND the
existing coursework package (`papers.py`, blueprint, assignments) and reuse the
paper API rather than duplicating it.

- `app/exam_ops.py` — exam scheduling, seating allocation, secure-print packaging,
  OMR/scan intake interface, proctoring-signal interface. All human-final; scan
  quality is never used to penalise a learner.
- `app/mocks.py` — blueprint-aligned multi-set mock generation, reusing `papers.py`.
- `app/groups.py` — configurable, explainable mastery/skill-balanced group
  composition.

NOTE: this module was reported BLOCKED in W1 by the host TCC restriction (the
agent could not read `papers.py`/blueprint/spec to extend them without guessing).
See Section 7. The intended contracts above stand for the next wave.

### 2.5 Learning misconception (`modules/learning/app/misconception.py`)

The d12 misconception path: a wrong answer yields a posed counterexample question
(a Socratic prompt), not a lecture; a correct answer is not "detonated"
(challenged); the PII guard rejects identifiers (for example e-mail) in payloads.
Model-backed identification runs through the gateway; offline degrades to a
conservative held state. A confidence floor is configurable.

### 2.6 Content dedup and artifacts (`modules/content/app/{dedup,artifacts}.py`)

- `dedup.py` — detects EXACT (sha256 over normalised text), NEAR_HASH (Jaccard
  over 3-shingles), and NEAR_SEMANTIC (cosine over an injected embedder, with a
  lexical-cosine fallback offline) duplicates. Verdicts are advisory only and
  carry `requires_human_approval=True` (the permission ladder never auto-removes
  content).
- `artifacts.py` — generates mind-maps (rooted node tree) and presentation
  outlines (ordered slides) via generate-and-verify: gateway-first with offline
  fallback, confidence gate (HELD below floor), structural + topic-coverage +
  child-safety verification (REJECTED on fail). Only verified artifacts are served.

---

## 3. Gateway hardening and module route registration

The gateway wall is the single choke point: every call passes the wall. W1 added
rate limiting, request schema validation, and a full enforcement pipeline, plus a
registry that makes the new modules routable.

- `spine/gateway/app/ratelimit.py` — per-principal + per-route limiting with two
  config-driven algorithms (`token_bucket`, `fixed_window`). Pluggable store;
  in-memory default; a Redis-backed store degrades gracefully to in-memory when no
  client is configured or the backend errors (never fails the request path). Keys
  carry only the opaque principal id. Clock is injectable for deterministic tests.
- `spine/gateway/app/validation.py` — stdlib-only per-route schema validation at
  the wall before routing. Strict-by-default (rejects undeclared fields), with
  required/type/bounds/enum/regex/nested-object/typed-array checks. Free-text
  fields are flagged so the wall routes them through child-safety. Error messages
  reference field PATHS only, never values (no PII leak).
- `spine/gateway/app/capabilities.py` — `CapabilityRegistry` and
  `build_default_registry()` register all fourteen capability modules
  (institution, scheduling, coursework, learning, content, learner-record,
  communication, intelligence-views, attendance, planning, classroom,
  teacher-growth, integration, feature-store) as routable capabilities. Each
  carries RBAC roles, an ABAC predicate (same-institution), a consent scope for
  cross-context reads, a `consequential` flag (exports require human approval), a
  per-route schema, and a rate-limit. Explicitly configured limits take precedence
  over capability defaults (`register_route(..., overwrite=False)`).
- `spine/gateway/app/wall.py` — `Wall.admit` runs one pipeline:
  route-exists -> authn(token) -> rate-limit -> schema-validate -> RBAC -> ABAC ->
  consent gate (cross-context) -> permission ladder (human approval for
  consequential) -> child-safety on free text -> audit. Every decision (allow or
  deny) is appended to an append-only audit sink carrying only the opaque id.
  Collaborators (token verifier, consent checker, child-safety screen, audit sink)
  are injected; with none wired, the wall degrades CLOSED (deny-all auth,
  block-all child-safety, in-memory append-only audit) so it never runs open by
  accident.

### Wiring the registry into the live gateway (integration step)

1. Register `build_default_registry()` capabilities into the live route map.
2. Construct `Wall(registry, limiter, verifier=<real token verifier>,
   consent=<real consent service>, child_safety=<real screen>,
   audit=<durable append-only sink>)`.
3. Load `RateLimiter.from_config(app/ratelimit_config.example.json)` with a Redis
   client built from `clss.gateway.<env>.redis_url`.

---

## 4. How the pieces connect

```
            web surface (Vidya)
                    |
   surfaces/web/lib/vidya.ts  ->  surfaces/web/app/api/vidya
                    |
                    v
        +-----------------------------+
        |   GATEWAY WALL (spine)       |
        |  ratelimit -> validation ->  |
        |  RBAC -> ABAC -> consent ->  |
        |  permission ladder ->        |
        |  child-safety -> audit       |
        +-----------------------------+
            |        |        |       |
            v        v        v       v
       attendance  planning classroom coursework
         |   risk   pacing   board     exam-ops
         |   recon  diary    polls     mocks
         |  staff   diff     live      groups
         |
         +--> substitution_needed_event --> scheduling intake
       learning (misconception)   content (dedup, artifacts)
```

- Vidya never calls a module directly; it calls through the gateway wall, which
  enforces authn, rate-limit, schema, RBAC/ABAC, consent, permission ladder,
  child-safety, and audit on every call.
- Attendance feeds scheduling NOT by a direct call but by emitting
  `substitution_needed_event` (immutable, append-only) once a human confirms an
  absence; scheduling consumes that event.
- Planning consumes mastery (from the intelligence spine) and the ontology
  (outcome refs) through injected adapters; it pushes advisory pacing signals into
  scheduling intake through an injected adapter.
- Classroom emits grasp/engagement events; learner-record and intelligence views
  consume them downstream (opaque id only, consent-gated).
- Content dedup/artifacts and learning misconception call models only through the
  gateway and only serve generate-and-verify output past the confidence gate.
- All behavioral payloads carry ONLY opaque `canonical_uuid`; PII keys are
  refused at the event layer and at the wall.

---

## 5. How to run

Prerequisites: a Python environment with `pytest`, and the web toolchain for the
surface. (Do not run installs as part of documentation; this section is for
operators.)

### Domain modules (Python)

Run each module's suite from a normally-permissioned environment (the W1 host
sandbox blocks in-place execution; see Section 7):

```
pytest modules/attendance/tests
pytest modules/planning/tests
pytest modules/classroom/tests
pytest modules/content/tests
pytest modules/learning/tests
pytest modules/coursework/tests   # after the coursework block is cleared
```

### Gateway

```
pytest spine/gateway/tests
```

Wire the registry and wall as in Section 3, then start the gateway service with
the env vars in Section 6 set.

### Web surface (Vidya)

Start the web surface with its toolchain; the Vidya API route and lib pick up the
model key from the server-side env (never `NEXT_PUBLIC_`). With no live key, Vidya
degrades to held/offline state.

---

## 6. Environment variables (names only)

Secrets are ENV-only and follow `clss.<app>.<env>.<purpose>`. No value is ever
hardcoded; no secret is exposed via `NEXT_PUBLIC_`.

Vidya / ai-fabric:

- `CLSS_AIFABRIC_DEV_GEMINI_API_KEY`

Attendance:

- `CLSS_ATTENDANCE_GATEWAY_URL`
- `CLSS_ATTENDANCE_ENV`
- `clss.attendance.<env>.gateway_token`
- `clss.attendance.<env>.event_signing_key`

Planning:

- `clss.planning.<env>.gateway_url`
- `clss.planning.<env>.gateway_token`
- `clss.planning.<env>.event_sink_dsn`
- `clss.planning.<env>.scheduling_intake_url`
- `clss.planning.<env>.intelligence_mastery_url`
- `clss.planning.<env>.ontology_resolver_url`

Classroom:

- `clss.classroom.<env>.gateway_url`
- `clss.classroom.<env>.event_sink_token`
- `clss.classroom.<env>.card_scan_hmac_key`
- `clss.classroom.<env>.safety_classifier_url`

Content / learning:

- `clss.content.<env>.fabric_key`
- `clss.learning.<env>.fabric_key`
- `CLSS_LEARNING_MISCONCEPTION_CONF_FLOOR` (optional, non-secret; overrides the
  misconception confidence floor)

Gateway:

- `clss.gateway.<env>.redis_url`

---

## 7. W1 environment constraints and follow-ups

The W1 host applied a macOS TCC (Privacy) restriction to the project tree under
`~/Documents`: pre-existing files could not be read, listed, appended to, renamed,
or deleted, while brand-new files could be created. This affected this wave in the
following documented ways (none are code defects):

- web-foundation: BLOCKED. No code written; the agent could not read existing
  files. Re-run after granting read access or moving the repo out of
  `~/Documents`.
- coursework-ext: BLOCKED. The agent could not read `papers.py`/blueprint/spec to
  EXTEND `exam_ops.py`/`mocks.py`/`groups.py` without guessing signatures, so it
  declined to overwrite. Intended contracts are in Section 2.4. Re-run after
  access is granted.
- attendance: `app/capture.py` and `app/risk.py` from a prior run were OS-locked
  and unreadable; the rest of the package and the full suite were authored and
  verified out-of-tree. If those two files diverge from the documented public
  APIs (capture: Status/Method/VoiceMark/DraftRoll/capture_*/confirm_roll/
  summarize_draft/CONFIDENCE_GATE; risk: detect_risks(history=...) -> findings
  with risk_kind in {consecutive,chronic,pattern}), regenerate or unlock them.
- planning / classroom / content / learning / gateway: built and verified
  out-of-tree (mirrored to a writable scratch dir, since `pytest` is not installed
  in-host and installs are forbidden, and the project tree is not executable
  in-host). Run the suites in a normal environment per Section 5.
- Documentation (this wave): `docs/BUILD.md`, `docs/RING2.md`, and
  `docs/TESTING.md` could not be read or appended to. Per the APPEND-not-rewrite
  rule, the W1 additions were written as sidecar files rather than overwriting the
  originals: see `docs/BUILD.append-w1.md` and `docs/TESTING.append-w1.md`. A
  maintainer with full filesystem access should fold those into `BUILD.md` and
  `TESTING.md`.

Resolution for the next wave (any one): grant the launching application Full Disk
Access in System Settings > Privacy and Security, OR move the repo out of the
`~/Documents` tree, then re-run the blocked modules.
