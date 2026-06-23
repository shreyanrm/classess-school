# Classess School — Slice 3: the Parent surface, the learner record, communication, and intelligence views

This is the build document for Ring 1, Slice 3. Where `docs/SLICE1.md` cut the
Student-Teacher learning loop and `docs/SLICE2.md` built the institutional Admin
layer, Slice 3 builds the **relationship and composition** layer: the surface a
parent works in, the record that composes a learner's evidence into a profile and
portable credentials, the communication layer that runs child-safety on every
free-text surface, and the intelligence views that turn the proactive loop into
calm, explainable dashboards.

It adds three capability modules (Learner record B8, Relationships &
communication B9, Intelligence views B11) and the Parent web surface. Slice 3
binds to the same frozen `@classess/contracts` boundary and the same twelve
invariants. Three of them do the most work here:

- **CONSENT gates every cross-context read.** The Parent surface is the consent
  authority and the partnership channel — never surveillance. No behavioural data
  reaches a parent, a record viewer, or an ask-anything answer without a
  satisfied consent + purpose check. The gate is fail-closed and denied-by-default.
- **CHILD-SAFETY runs on every free-text surface.** The companion, the hub, and
  ask-anything all screen every message first: moderation, crisis detection, and
  escalation to qualified humans. There is no path to an unmonitored channel.
- **Plain language for learners and parents.** No raw number, score, percentage,
  or formula is ever surfaced to a learner or a parent. Mastery is shown as
  independent-vs-support-dependent in words, with evidence behind it.

The slice is built on generic labels throughout (Parent, Child A / B / C,
Section 10-B); no PII, no real pricing, no board lock-in, no emoji, no
exclamation marks in product copy.

---

## 1. The consent-authority + partnership model

A parent is not a watcher. The Parent surface is built as a partnership channel:
it shows a child's pride and progress, the proof of what a child can now do alone,
the feedback a human released, and activities to learn alongside — and it is the
place where consent is exercised, not bypassed.

The model is enforced in **data, not just UI**:

- `selectChildData()` returns `null` for any unconsented or unknown child, so no
  behavioural data can flow through the surface at all. The page renders a calm
  "not shared yet" / consent-gated state instead of an error. Child A and Child B
  are consented in the mock; Child C is deliberately unconsented to exercise the
  gate.
- Every record read (B8) passes `app/access.py`, a denied-by-default consent +
  purpose gate that checks scope, purpose, audience, and validity, and raises
  `ConsentDenied` on a failed read. The reason carries no PII.
- Every cross-context partnership read (B9 `parent_partnership.read_child_context`)
  is consent-gated fail-closed, and a **surveillance-shaped purpose is refused
  even with a valid consent grant**. Consent permits partnership, never monitoring.
- Every ask-anything answer (B11) is consent-gated before a number is resolved.

All identity is opaque: `child-a` / `child-b` / `child-c` stand in for the
`canonical_uuid`; never a name, never PII.

---

## 2. Learner record — `modules/learner-record` (B8)

The School-facing **composition of the evidence graph**: the evidence-linked
profile, the portfolio, and verifiable credentials. B8 **reads** governed,
consent + purpose-gated views of the learner graph and the evidence store — never
bulk, never PII — and composes them into a record the School can show. It **never
authors mastery** (that is spine A3) and **never computes a score**. A pure,
import-safe Python package (stdlib-only on the deterministic path) under
`modules/learner-record`, matching the sibling-module layout (`app/` subpackage,
`conftest.py`, `pytest.ini`, env-name-only config). 50 tests pass.

- **`access.py`** — the consent + purpose gate that runs before every read.
  Denied-by-default; checks scope, purpose, audience, and validity (a revoked or
  expired grant is denied; a parent in the consented audience is allowed).
  `require()` raises `ConsentDenied`; the reason never carries PII.
- **`profile.py`** — composes governed mastery views into an evidence-linked
  profile that **foregrounds independent vs support-dependent in plain language
  with no number or formula**. `assert_plain_language` is a boundary guard that
  rejects any digit, percent, or formula in learner-facing text. Every item
  carries its source lineage and its permission controls (`consent_id`,
  `visible_to`, `learner_controlled`, `why_visible`). There is no score field on
  an item.
- **`portfolio.py`** — curated artifacts requiring **provenance** (an artifact
  with no source events cannot be added). The shared view is gated
  (denied-by-default); a caption that contains a raw score is rejected. Curation
  is append-only.
- **`credentials.py`** — **verifiable, portable, learner-controlled** credentials.
  No signing key configured -> the credential is `draft` and **not verifiable**
  (never faked). With a key, HMAC-over-canonical-JSON sign/verify with a
  constant-time compare; a tampered, expired, or revoked credential fails verify.
  Export to anyone but the holder is gated; a self-export is portable, PII-free,
  and carries full lineage.
- **`events.py`** — emits `portfolio.artifact_added`, `portfolio.artifact_featured`,
  `credential.issued`, `credential.revoked` on the attributed, append-only
  envelope (purpose `mastery`). The envelope is PII-asserted (a PII key is
  rejected); a statement that contains a number is rejected; the emitter degrades
  to an in-memory append-only sink.
- **`config.py`** — environment-only configuration, read by name; an empty
  settings object is fully degraded.

**Owns:** the evidence-linked profile, the portfolio, verifiable credentials, the
consent + purpose read gate. **Exposes:** the access, profile, portfolio,
credentials, and events surfaces (Python `app/`). **Consumes:** governed
read-views of the learner graph + evidence store (A3) through the gateway; the
event envelope; opaque ids only. B8 deliberately authors no mastery and computes
no score.

**The proof artifact.** A credential (B8 `credentials.py`) and a portfolio
artifact (B8 `portfolio.py`) are the record-layer proof; the **Proof artifact**
on the Parent surface (`app/_components/ProofArtifact.tsx`) is the calm,
parent-facing rendering of that proof — see §5.

**Contract note (consistent with B1 / B2).** The portfolio and credential type
strings ride the exact spine envelope under the module namespace until the
versioned `EventType` union adopts canonical names; no envelope change is needed.

---

## 3. Relationships & communication — `modules/communication` (B9)

The relationships layer: the bounded companion / care surface, parent engagement
and parent-teacher partnership, the communication hub, multilingual translation,
and **safeguarding — the child-safety subsystem that runs on every free-text
surface**. A dependency-free, import-safe Python package under
`modules/communication`, following the sibling layout. 48 tests pass; import-safe
on bare `python3`.

Four non-negotiables run through every surface here:

- **The companion is bounded.** Every reply — scripted or model-generated —
  passes a boundary wall (`check_boundaries`) that rejects dependence /
  exclusivity / manipulation wholesale and points the learner back toward people
  and independent effort.
- **Serious matters escalate to qualified humans.** Child-safety screens every
  message first; a flagged or crisis message is handed to a qualified human, never
  counselled by a bot.
- **No unmonitored channels.** There is no constructor for an un-screened
  free-text channel; `open_channel` refuses a guard-less channel structurally and
  `MonitoredChannel.admit` is the only ingress.
- **The parent surface is partnership and pride, never surveillance.**

- **`safeguarding.py`** — the child-safety subsystem: a deterministic on-device
  moderation + crisis classifier (`classify`) that **fails safe** (flags up under
  ambiguity, never silences a crisis), escalation always routed to a qualified
  human (`escalate` / `screen`, `pending_human`, never auto-resolved), and
  structurally no unmonitored channels. Directed self-harm is treated as crisis;
  `worst()` picks the highest severity; the on-device fallback never silences a
  crisis.
- **`companion.py`** — the role-shaped, bounded companion. `check_boundaries`
  rejects any dependence / exclusivity / manipulation reply; `respond` screens
  every message and escalates serious matters instead of counselling them;
  `vet_generated_reply` is the second wall over an orchestrator candidate.
  Degrades to a vetted, scripted, anti-dependence path with no orchestrator. The
  companion always has a safeguard and never counsels a crisis.
- **`hub.py`** — the communication hub. `post` always screens (no unmonitored
  channel); a flagged message is admitted with an escalation, never silently
  dropped; `route_to_task` turns a message into an **owned, tracked task** with an
  owner, due date, and why, advanced only by a human (permission ladder).
  Cross-context routing is consent-gated.
- **`parent_partnership.py`** — parent engagement framed as **partnership +
  pride** in plain language (no raw number / formula). `read_child_context` gates
  every cross-context read on a satisfied consent grant (fail-closed) and
  **refuses surveillance purposes even with consent**. A revoked / mismatched /
  expired grant is denied.
- **`translation.py`** — the multilingual + code-switching interface. Preserves
  protected subject terminology verbatim (`mask` / `restore` round-trip), detects
  and preserves code-switch spans, and degrades to a content-preserving
  pass-through that never drops or garbles text.
- **`events.py`** — emits `message.sent`, `meeting.scheduled`,
  `sentiment.observed`, `safeguarding.escalated` on the attributed, append-only
  envelope. Opaque ids only — **never the message body**, only its safety
  verdict; `message.sent` refuses an unscreened message; a safeguarding
  escalation rides the `intervention` purpose.

**Owns:** the bounded companion, safeguarding, the hub, parent partnership,
translation. **Exposes:** those five surfaces plus events. **Consumes:** the A4
orchestrator, the A7 safety service, the A1 consent authority, the A5 workflow
engine, and the translation provider — all through the gateway; opaque ids only.

---

## 4. Intelligence views — `modules/intelligence-views` (B11)

The dashboards and analytics composed over the spine proactive loop (A5) and a
governed semantic layer. B11 turns observe -> interpret -> recommend into "here is
what I found, and what to do": a calm, ranked set of alerts, each carrying its
evidence, a confidence band, the owner, a due date, the consequence of ignoring,
and the plain-language why-am-i-seeing-this. It owns no spine concern; it only
COMPOSES governed outputs. An import-safe Python package under
`modules/intelligence-views`. 49 tests pass offline.

- **`semantic_layer.py`** — the keystone. Every number on every screen resolves
  through ONE registry: a metric is defined exactly once (key, plain-language
  label + definition, single compute function, grain, unit, and learner-safe
  banding). Registering two definitions under one key raises
  `MetricRedefinitionError`; an identical definition is idempotent; an unknown
  metric is refused. So the cohort's "mastery" is the same number wherever it
  appears, and a non-learner-safe metric is banded into plain language with the
  raw value kept internal.
- **`dashboards.py`** — composes confirmed cohort gaps into ranked alerts that
  **ARE spine workflow Recommendation objects** (minted by
  `build_cohort_weakness_recommendation` through a name-collision-safe spine
  bridge), so the permission ladder and the full provenance set hold by
  construction. Each alert carries evidence summary + linked evidence_refs,
  confidence band, owner (role + opaque ref), consequence, why-am-i-seeing-this,
  suggested action, and a ladder stage derived from the action effect. An alert
  **never auto-fires and is never `safe_automatic`**; a single bad score raises no
  alert; a strong cohort raises no alert.
- **`study_quadrant.py`** — the effort x outcome quadrant, four differentiated
  responses (high-effort/low-outcome -> `needs_support`; low/low ->
  `needs_reengage`; strong -> `thriving`). Deterministic, explainable,
  learner-scoped.
- **`target_analytics.py`** — a human-set target vs the forecast trajectory, with
  gap-to-target, full explainability, owner, and due date, sorted
  most-at-risk-first; an invalid target is rejected.
- **`prediction.py`** — a trajectory / forecast from mastery + coverage:
  reproducible, bounded, advisory. Strong -> on-track / ahead;
  support-dependent -> at-risk / behind; thin evidence -> low confidence; carries
  evidence + assumptions + why.
- **`ask_anything.py`** — a governed natural-language query over the semantic
  layer: **child-safety screen -> consent gate -> defined-metric resolution ->
  learner-safe number gating**, fail-closed. The answer equals the direct
  semantic-layer number; an unscreened question is refused; a flagged question
  escalates to a human; an unknown metric is refused, not invented; a learner
  audience never sees a raw unsafe number but does see learner-safe coverage.
- **`spine_workflow.py`** — a bridge that loads the spine workflow / intelligence
  builders as **source** (no install or build) under private namespaces, so the
  module's own `app` package is never shadowed. No spine file is modified.

**Owns:** the semantic layer, the dashboards, the study quadrant, target
analytics, prediction, ask-anything. **Exposes:** those surfaces. **Consumes:**
the spine A5 workflow builders and A3 projections as source / through the gateway;
the feature store, semantic-layer service, and consent service by env name only.

**Ladder note.** The spine cohort-weakness builder classifies its `prepare`
effect to the `recommend` rung (fail-closed: `prepare_support_material` is not on
the safe-automatic allow-list), so the dashboard alert's `ladder_stage` is in
{recommend, prepare} and never `safe_automatic` — INVARIANT 8 holds either way.

---

## 5. The Parent surface — `surfaces/web/app/parent`

The parent's surface on the v4 design system — **partnership and pride, not
surveillance** — reachable via the rail's role switcher, with Vidya docked on
every page through `SurfaceShell`. `tsc --noEmit` is clean; the full web vitest
suite is green (27/27, 11 new).

- **`parent/page.tsx` (Today)** — three calm "actions this week" rendered as
  `BriefingCard`s in the parent's own language, each with a where-to-go-next link
  and a consent framing line.
- **`parent/child/page.tsx` (Child view)** — one timeline per child with the
  **Child switcher** (a one-click switch re-renders the whole surface via React
  state + `selectChildData`), the most-recent **Proof artifact**, a progress
  timeline, and strengths and support areas — all plain language, with an
  `IgniteDot` marking what a child can now do alone.
- **`parent/reports/page.tsx` (Reports)** — parent-specific feedback, celebration
  points, and next steps, with an empty state and a "released by a human, never
  automatically" note.
- **`parent/together/page.tsx` (Together)** — learn-alongside activities tied to
  real next steps, plus parent-teacher meeting prep (scheduled vs unscheduled
  states).
- **`parent/loading.tsx` / `parent/error.tsx`** — first-class loading and error
  states; consent-gated, empty, and offline states are rendered inline.

Shared components:

- **`app/_components/ChildSwitcher.tsx`** — consent-aware; a locked (unconsented)
  child reads "Not shared yet", never an error.
- **`app/_components/ProofArtifact.tsx`** — the parent-facing proof: a
  `SpotlightCard` + `IgniteDot` showing what a child can now do alone. It is
  **child-triggerable** and the **parent-initiated share never auto-fires**
  (permission ladder).

Data lives in `lib/parentData.ts` — the typed mock (Child A / B / C, generic
sections) plus the tested child-switch logic (`findChild`, `resolveChildId`,
`selectChildData` with consent gating). The live path remains the gateway + event
store (env var names in `lib/runtime.ts`); `parentData.ts` is the graceful
degradation fallback with no live keys / DB. The surface never touches the event
store or PII vault directly.

---

## 6. The proof artifact

The proof artifact is the through-line of the slice: evidence over assertion,
made plain enough for a parent.

1. A learner's act becomes immutable evidence (Slice 1).
2. B8 composes that evidence into a portfolio artifact (with provenance) or a
   verifiable, learner-controlled credential.
3. The parent surface renders the most-recent proof (`ProofArtifact.tsx`) as what
   a child can now do **alone** — `IgniteDot` marks the independent milestone, in
   plain language, no number.
4. Sharing the proof is **parent-initiated and never auto-fires**; a credential
   export to anyone but the holder is consent-gated; a learner self-export is
   portable, PII-free, and carries full lineage.

So a proof shown to a parent is always traceable to its source events, always
consented, always plain language, and never shared without a human acting.

---

## 7. Consent and child-safety across the slice

| Surface | Consent gate | Child-safety |
|---|---|---|
| Parent surface | `selectChildData()` returns null for any unconsented / unknown child; data cannot leak through the UI | free-text to Vidya routes through the docked companion (B9) |
| Learner record (B8) | `access.require()` denied-by-default; raises `ConsentDenied`; export gated | profile / portfolio reject raw numbers in learner-facing text |
| Communication (B9) | `parent_partnership.read_child_context` fail-closed; surveillance purpose refused even with consent; cross-context hub routing gated | `safeguarding` screens every message; no unmonitored channel; flagged / crisis escalates to a qualified human, never auto-resolved |
| Intelligence views (B11) | `ask_anything` consent-gates before resolving a number | `ask_anything` screens each question; unscreened refused; flagged escalates |

---

## 8. Human-authority gates (INVARIANT 8)

```
Recommend → Prepare → Execute-with-permission → Safe-automatic
```

Every consequential act in Slice 3 stops at a human:

- **Sharing a proof / exporting a credential** (B8 + Parent surface) is
  parent- or learner-initiated and never auto-fires; export to a non-holder is
  consent-gated.
- **Advancing a tracked task / acting on an escalation** (B9 `hub.py` /
  `safeguarding.py`) is human-owned; the system prepares and routes but never
  auto-resolves. A crisis is never bot-handled.
- **Dashboard alerts** (B11) are non-consequential surfacing steps; they never
  auto-fire and are never `safe_automatic`. Sending support material is a
  separate, consequential recommendation that needs explicit human approval.

---

## 9. Environment variables (names only — never a value)

All secrets are environment-only and follow `clss.<app>.<env>.<purpose>`; the OS
key is the dotted name uppercased with dots / dashes -> underscores. None is
hardcoded; absence degrades gracefully behind a clear interface. No
`NEXT_PUBLIC_` secret exists in this slice; nothing is client-exposed.

| Module | Env var names (dotted → OS) |
|---|---|
| learner-record (B8) | `clss.learner-record.dev.gateway_url`, `.gateway_token`, `.graph_read_url`, `.consent_authority_url`, `.event_sink_url`, `.credential_signing_key` → `CLSS_LEARNER_RECORD_DEV_*` |
| communication (B9) | `clss.communication.dev.gateway_url`, `.event_sink_url`, `.database_url`, `.orchestrator_url`, `.safety_url`, `.consent_url`, `.workflow_url`, `.translation_url` → `CLSS_COMMUNICATION_DEV_*` |
| intelligence-views (B11) | `clss.intelligence_views.dev.gateway_url`, `.feature_store_url`, `.semantic_layer_url`, `.consent_service_url`, `.ask_model_route` → `CLSS_INTELLIGENCE_VIEWS_DEV_*` |
| parent surface | none new — reuses the web gateway env names in `lib/runtime.ts` |

Absence behaviour: the credential signing key absent -> credentials issued
`draft` / not verifiable; the safety service absent -> the on-device classifier
floor (fail-safe); the gateway / read services absent -> in-memory governed-view
fixtures and an in-memory append-only sink; the consent authority absent -> the
in-process gate (still denied-by-default).

---

## 10. Running it

> Do not run installers or builds inside a single lane during the parallel build;
> the orchestrator installs and builds centrally. The steps below are what the
> central setup enables.

### 10.1 The Parent surface

```bash
# from surfaces/web, after the central npm install
npm run dev          # next dev — serves /parent and its destinations
```

Open `/parent` for Today, then `/parent/child`, `/parent/reports`, and
`/parent/together`. Child A and B are consented; Child C renders the calm "not
shared yet" gate. Verification used `tsc --noEmit` (clean) and the web vitest
suite (27 passing, 11 new in `lib/__tests__/parentData.test.ts`).

### 10.2 The Python modules (tests)

Each module degrades to offline, deterministic behaviour with no provider.

```bash
python -m pytest modules/learner-record       # 50 tests, stdlib-only path
python -m pytest modules/communication        # 48 tests, dependency-free
python -m pytest modules/intelligence-views    # 49 tests (spine consumed as source)
```

`learner-record` and `communication` import on bare `python3` with no
third-party deps. `intelligence-views` uses the repo venv at `.venv` (it consumes
the spine `intelligence` / `workflow` packages as source — no install or build is
run, per the law — and loads them under private namespaces so the module's own
`app` package is never shadowed).

---

## 11. What this slice proves, and what it defers

It proves the relationship and composition layer end to end without compromising
the invariants: a parent sees pride and proof, never a raw number and never
without consent; a learner's evidence composes into an evidence-linked profile
and a portable, verifiable credential that is never faked without a key; every
free-text surface screens for safety first and escalates a crisis to a qualified
human; and every number on every dashboard resolves through one definition so it
reads the same everywhere.

It defers — behind named env vars, with no re-architecture — the live gateway
egress for B8 / B9 / B11 events, the live governed read-view and consent-authority
services (in-memory fixtures and the in-process denied-by-default gate stand in),
the asymmetric credential signing that swaps in behind the stable sign/verify
interface (HMAC-over-canonical-JSON is the mechanism placeholder), the A7 safety
service (the on-device fail-safe classifier is the floor), and the live A4
orchestrator and translation provider. As in Slice 1 / 2, the closed v1
`EventType` union does not yet carry the portfolio / credential / message /
meeting / sentiment / safeguarding payloads; they ride the exact spine envelope
with namespaced type strings until the contracts owner adds them upstream.
</content>
</invoke>
