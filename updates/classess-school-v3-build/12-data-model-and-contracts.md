# 12 · Data Model and Contracts

## The three store classes

1. **Canonical / platform (secure core).**
   - **PII vault** — names, contacts, government IDs, faces. Separate, more-restricted
     store. Maps `canonical_uuid ↔ PII`. Nothing else holds PII.
   - **`app_memberships`** — which person plays which role in which institution/context
     (scoped, time-bound). Opaque UUIDs only.
   - **`consents`** — consent + purpose grants per person/context/scope, age-tier aware,
     revocable; stamped onto events and checked on every cross-context read.
   - **`events`** — append-only, immutable, attributed. The firehose. Carries
     `canonical_uuid`, never PII.
   - **`evidence`** — the typed evidence records conclusions link to (attempts, scores,
     observations) with the independent-vs-supported flag.
   - **`audit_log`** — immutable record of privileged actions; break-glass entries.
   - **Derived projections (read models, rebuildable from events):** `profiles`,
     `learner_graph` (the knowledge map), `feature_store` (mastery/gap features). Opaque
     UUID + behavioral data only.

2. **Operational (per capability module).** Each module owns its Postgres schema (+
   pgvector for content/semantic search). Modules read governed scoped views down and emit
   events up; **no module bulk-reads the canonical store** (the seam, `03`).

3. **High-velocity.** Supabase Realtime (live attendance, polls, notifications, chat),
   Redis (cache, sessions, OTP, rate-limit, the cached engine reads surfaces use offline),
   Storage (submissions, recordings, scanned scripts, generated media).

## The PII rule (invariants 1–2, restated as a build rule)

- A row outside the PII vault may carry `canonical_uuid` + behavioral fields and **must
  not** carry a name, contact, ID, or face.
- `canonical_uuid` is random, never derived from PII.
- Deletion = drop the PII vault row → the link is severed; de-identified aggregate
  behavior remains and is unlinkable. Every store is designed so this holds.
- Reviewer test on any new table/column: "does this leak PII outside the vault or let
  someone re-link an opaque UUID to a person?" If yes, redesign.

## The `/contracts` package (lock before parallel work)

The shared, versioned source of truth all agents bind to. **Contracts are settled in
Wave 0 and changed only by a deliberate, reviewed version bump** — never edited freely
mid-parallel-build.

- `events/` — the event schemas + catalog (below). Append-only; additive evolution only.
- `evidence/` — evidence record types + the independent-vs-supported flag.
- `openapi/` — the gateway + module API surface (typed, documented). Surfaces generate a
  typed client from this; they never hand-roll calls.
- `db/` — canonical schema + the governed read-view definitions (the faucet).
- `mastery/` `gaps/` `evaluation/` `ontology/` — the engine I/O contracts (the Zod/typed
  schemas the repo already has: `AttemptMode` independent/supported, gap types, mastery
  dimensions, evaluation modes, ontology nodes/edges). One definition, consumed by the
  Python engine and the typed surface client alike.
- `tokens/` — the v4.1 design tokens (`tokens.json`) consumed by the design-system
  package.
- `capabilities/` — the capability registry contracts (`11`): I/O, ladder level, consent,
  events, track.

## The event catalog (emit from line one)

Every meaningful action emits one clean, attributed, consent-stamped event. Core families
(extend per module, additive-only):

- **Identity/consent:** `person.created` · `membership.granted` · `consent.granted` ·
  `consent.revoked`.
- **Learning:** `attempt` (carries `mode: independent|supported`, difficulty, assistance
  level, topic, outcome) · `lesson.viewed` · `prediction.committed` ·
  `misconception.detected` · `misconception.resolved` · `teachback.completed` ·
  `retrieval.completed`.
- **Mastery/evidence:** `evidence.recorded` · `mastery.updated` · `gap.detected` ·
  `gap.resolved`.
- **Coursework/assessment:** `assignment.created` · `submission.created` ·
  `assessment.submitted` · `score` · `evaluation.completed` · `moderation.approved` ·
  `paper.generated`.
- **Content:** `content.generated` · `content.verified` · `content.rejected` (failed the
  gate).
- **Attendance/ops:** `attendance.marked` · `attendance.risk` · `substitution.proposed` ·
  `timetable.generated` · `pacing.behind`.
- **Workflow/agent:** `recommendation.created` · `recommendation.actioned` ·
  `intervention.created` · `intervention.outcome` · `capability.invoked` · `approval.given`.
- **Comms/relationship:** `message.sent` · `ptm.scheduled` · `ptm.completed` ·
  `action.assigned`.
- **System:** `surface.viewed` · `audit.entry` · `break_glass.used`.

**Event envelope (every event):** `id`, `type`, `occurred_at`, `actor canonical_uuid`,
`subject canonical_uuid`, `context` (institution/grade/section scope), `consent_ref`,
`payload` (typed per type), `source` (surface/capability), `trace_id` (Langfuse link).
Append-only; never mutated; additive schema evolution only.

## The per-surface event map (build rule)

Each surface in `06`–`09` names the events it emits under *Reads / Writes / Emits*. The
binding rule: **if a surface performs a consequential action and does not emit its event,
it is not done.** The intelligence can only learn from what is recorded — a missing event
is a silent hole in every downstream insight. The master checklist (`15`) tracks event
emission per surface as a done criterion.

## Governed read views (the faucet)

Surfaces and modules read **scoped, consent-checked views**, never the raw canonical
store: `learner_mastery_view`, `learner_graph_view`, `class_mastery_view`,
`coverage_view`, `trajectory_view`, `attendance_risk_view`, `proactive_feed_view`. Each
view enforces RBAC/ABAC + consent at the gateway and returns opaque-UUID behavioral data.
The MasteryView/KnowledgeView/StudyQuadrant components (`10`) bind to these — never to the
engine internals and never to a TypeScript re-implementation.

## Seed / mock data discipline

All seed and demo data is fictional and scrubbed (`02`): fictional institutions
("Northfield International"), fictional learners ("Aanya," "Mr. Rao"), `₹X,XXX` pricing, no
real names, no codenames. Seed data exercises every state (empty/loading/error/offline/
permission) and every confidence band so the UI is provably complete.
