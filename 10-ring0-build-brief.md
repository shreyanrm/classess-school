# Classess School — Ring 0 Build Brief

**Audience:** Claude Code (founder-side build agent).
**Purpose:** Stand up Ring 0 — the secure base of Classess School — complete and correct, before any feature. Stop at the Ring 0 done-line. The first vertical slice (Student ⇄ Teacher) rides on this next.

---

## 0. What you are building

Classess School is one citizen of the Dot eVentures education ecosystem. Ring 0 is its base: the spine contracts plus the secure core, built once, with the event contract immutable from the first commit. This is not an MVP and not a stub — every line is production-grade. You are building the parts that must be exactly right and must never leak credentials or IP. Breadth (surfaces, non-sensitive module logic) is handed to the developer team afterward, against the contracts you produce here.

---

## 1. Altitude — read before writing anything

- The ecosystem is the entity. KGtoPG is the platform citizen. Classess School is a citizen built on it.
- Spine = ecosystem-owned: identity, ontology, the event/evidence contract, the AI fabric, governance. School-specific = capability modules + role surfaces.
- Hard rule: a School module never owns a spine concern. If you are about to place identity, the event contract, the ontology, or the evidence/mastery engine inside a School module, stop — it belongs to the spine, and fusing it to School blocks the next citizen (Classess Learner) from reusing it.

---

## 2. Non-negotiable security invariants

These are checkable. Ring 0 is not done until every one holds. A merge that violates any is rejected.

1. **PII is vaulted and segregated.** Canonical identity (PII) lives in a separate, more-restricted store. The event store, profile, graph, and feature store carry only the opaque `canonical_uuid` and behavioral data — never PII.
2. **The canonical UUID is opaque.** It is a random id, never derived from PII. Deletion drops the PII vault row, severing the link; de-identified aggregate behavior remains and is unlinkable to a person.
3. **Every call passes the gateway.** No service is reachable unauthenticated. RBAC + ABAC are enforced at the wall, not inside services. A verified identity token is required for every request.
4. **Secrets are environment-only.** Infisical / env vars exclusively. Never in code, config, logs, error messages, or chat. Key naming: `clss.<app>.<env>.<purpose>`. Rotate immediately on any exposure.
5. **The event contract is immutable and append-only from line one.** Emit a clean, attributed event for every meaningful action. Events are never mutated or deleted in place.
6. **Consent is a primitive.** Captured at the identity layer, stamped on every event, and gates every cross-context read. No read proceeds without a satisfied consent + purpose check.
7. **Generate-and-verify.** No generated content is served unverified. A confidence gate refuses anything that fails verification. (Substrate is Ring 1; the contract for it is defined now.)
8. **Permission ladder on any agent action:** Recommend → Prepare → Execute-with-permission → Safe-automatic. Anything that sends, submits, publishes, deletes, or charges requires explicit human approval. Agents hold no credentials and never touch data directly — they invoke governed, least-privilege capabilities.
9. **Audit is immutable; privileged actions are break-glass.** Every privileged action is recorded and reviewable.
10. **Encryption in transit and at rest; tenant isolation** with logical separation per institution.
11. **Two tracks are never conflated.** Track 1 (external LLM routing) and Track 2 (proprietary / edge models) are separate in gateway config, with different ownership. The Track 2 slot exists from the start and is filled later — no re-architecture.
12. **Confidentiality discipline.** Forbidden codenames, personal names, board lock-in language, and placeholder text must never appear in any developer-facing or team-facing artifact you generate. The confidential orchestrator is never named in those outputs; the team interacts with it only through the API.

---

## 3. Ring 0 scope and build order (dependency-ordered)

Build strictly in this order. Each step states what it produces and when it is done.

**Step 0 — Repo, secrets, CI.**
Monorepo (see §4). Infisical wired. CI/CD from the GitHub org. No application code yet.
*Done when:* a clean pipeline runs, secrets resolve from Infisical, nothing is hardcoded.

**Step 1 — The `/contracts` package (the gate).**
Event + evidence schemas; OpenAPI per capability; the canonical DB schemas; the v4 design tokens. This is the single source of truth every later agent and the developer team binds to.
*Done when:* contracts compile, types are exported, and a consumer can import them.

**Step 2 — Operational data substrate.**
Supabase (Postgres + pgvector + Auth + Realtime + Storage) provisioned. Redis for cache, sessions, OTP, rate-limit. Migrations under version control.
*Done when:* migrations apply cleanly to a fresh project and roll back.

**Step 3 — Identity service.**
Canonical user, AppMembership (User × App × Role × scope, time-bound), RBAC + ABAC, consent. Supabase Auth as the mechanism, phone-OTP-first (plus Google / Apple). PII vault segregated per §2.
*Done when:* a user can sign in, a membership scopes their access, and consent is recorded and queryable.

**Step 4 — API gateway skeleton.**
One wall: token verification, RBAC/ABAC enforcement, schema validation, audit, routing.
*Done when:* no route is reachable without a valid token + satisfied policy, and every call is audited.

**Step 5 — Immutable event store + the event/evidence write-path.**
Append-only event store, attributed (`app · canonical_uuid · type · purpose · consent_ref`). The evidence contract write-path, ready for the first slice to emit into.
*Done when:* a sample attributed event is emitted, stored immutably, and reads back through a governed, scoped view only.

**Ring 0 done-line.** When Steps 0–5 hold and the §8 checklist passes, the base exists. Do not start feature modules. The Student ⇄ Teacher slice (Ring 1) is the next instruction.

---

## 4. Repo / monorepo layout

```
classess/
  contracts/            # SINGLE SOURCE OF TRUTH — schemas, OpenAPI, events, tokens
    events/             # event + evidence schemas (immutable, versioned)
    openapi/            # per-capability API specs
    db/                 # canonical DB schemas + migrations
    tokens/             # v4 design tokens
  spine/                # SECURE CORE — founder + Claude Code only
    identity/           # canonical user, AppMembership, RBAC/ABAC, consent
    gateway/            # the wall: auth, policy, validation, audit, routing
    event-store/        # immutable append-only store + write-path
    ai-fabric/          # model router (Ring 1) — Track 1 / Track 2 config separated
    intelligence/       # evidence/mastery/gap engines (Ring 1) — projections from events
    governance/         # audit, break-glass, secrets policy, AI control centre
  modules/              # capability modules (Ring 1+) — own their operational tables
  surfaces/             # role surfaces (developer team) — compose, own no logic
  ops/                  # provisioning records, env var inventory, runbooks
```

`spine/` and `contracts/` are never handed to developers. `surfaces/` and the non-sensitive parts of `modules/` are their lanes, against `contracts/`.

---

## 5. Data model — three store classes

**Canonical / platform (secure core — developers never touch directly).** Materialized in Ring 0:

- *PII vault* (separate, restricted): `canonical_uuid` (PK, random/opaque), phone, name, dob, and other PII — encrypted, access-logged. This is the only place `canonical_uuid` maps to a person.
- `app_memberships`: `canonical_uuid`, app, role, scope, granted_at, revoked_at.
- `consents`: `canonical_uuid`, scope, purpose, age_tier, granted_by, granted_at, revoked_at.
- `events` (append-only, immutable, partitioned): `event_id`, `canonical_uuid` (opaque ref only), app, type, purpose, `consent_ref`, payload (jsonb), occurred_at, recorded_at.
- `audit_log` (immutable).
- *Derived projections* (built by replaying `events`, never authored directly — Ring 1+): `profiles`, `learner_graph`, `feature_store`.

**Operational (per capability module — Postgres + pgvector, behind the gateway).** Contract-defined now, materialized as each slice arrives: institution + hierarchy, ontology + prerequisite graph (pgvector), content metadata, timetable, attendance, coursework, gradebook, learner record (school-facing view), policies. Each module owns its own tables. Modules never share tables — only events.

**High-velocity / ephemeral:** Supabase Realtime (chat, AI threads, notifications, live session events, presence, leaderboards) · Redis (cache, sessions, OTP, rate-limit) · Supabase Storage + CDN (media, generated assets, scanned scripts).

**The schema-level rule:** the PII vault is physically separate from the behavioral event store, and every behavioral row is keyed by `canonical_uuid` with no PII present.

---

## 6. Stack and provisioning authority

**Stack:** Supabase (Postgres + pgvector + Auth + Realtime + Storage) · Redis · FastAPI services (typed, OpenAPI-documented, feature-modular in one deployable) · LiteLLM router (Ring 1, Track 1 / Track 2 config separated) · Langfuse (LLM observability) · Infisical (secrets) · Expo / React (surfaces) · CI/CD from the GitHub org. No CDN dependencies in production code; CDN only in review artifacts with self-hosting noted.

**Provisioning authority — you are cleared to take initiative.** Set up the Supabase project, install packages, scaffold integrations, and request whatever access you need (API keys, service accounts, provider credentials). Two constraints, no exceptions:

- Never hold or hardcode a secret. When you need a credential, name the env var (`clss.<app>.<env>.<purpose>`), tell the founder which key to place in Infisical, and read it from the environment. Credentials are entered into Infisical by the founder — never into chat, code, or config.
- Record everything you provision in `ops/` — the Supabase project, the env var inventory (names only), and any external integration — so the setup is reproducible and auditable.

**Env vars to expect (names only, values via Infisical):** Supabase URL + service/anon keys, the database URL, the Redis URL, the LLM provider keys (routed via the gateway, Ring 1), Google TTS (Ring 1), and the WhatsApp channel (Ring 2).

---

## 7. Working method

1. **Contracts first.** Write `/contracts` before any parallel work. Load the relevant skills (brand, catalogs, schemas, rubrics). Note: the v4 brand skill needs regenerating — the currently loadable one is stale v3; do not apply v3.
2. **Decompose by bounded context, parallelize across disjoint modules.** One agent per module or slice-end, each in its own git worktree, each handed a tight spec + the contracts + its skills. Clean boundaries are what keep parallel agents from colliding.
3. **The secure core gets the most careful, most reviewed passes** — never a careless parallel agent.
4. **Every merge passes two gates:** a verification pass (the §2 invariants hold, the event contract holds, the confidence gate is in place) and a confidentiality scrub (forbidden codenames, personal names, board lock-in language, plaintext secrets) before it lands.

The loop: planner defines the slice + contracts → parallel module agents in worktrees → integrate at the contract boundary → verify + scrub → merge.

---

## 8. Definition of done for Ring 0

- [ ] CI green; secrets resolve from Infisical; nothing hardcoded.
- [ ] `/contracts` compiles and exports types; a consumer can import it.
- [ ] Supabase + Redis provisioned; migrations apply and roll back on a fresh project.
- [ ] A user signs in (phone-OTP), a membership scopes access, consent is recorded.
- [ ] No route is reachable without a valid token + satisfied RBAC/ABAC policy; every call is audited.
- [ ] A sample attributed event is emitted, stored immutably, and reads back only through a governed, scoped view.
- [ ] PII vault is segregated; no behavioral store carries PII; deleting the vault row leaves events unlinkable.
- [ ] Confidentiality scrub passes on every artifact generated.
- [ ] `ops/` documents the full provisioned setup.

When this checklist passes, stop and report. The base exists.

---

## 9. The build lanes (Claude Code agents)

In this build Claude Code builds the entire stack — UI, backend, AI, data, auth — running each lane as a parallel agent against the contracts. The `/contracts` package is the gate that lets the lanes run at once: the instant it lands, surface agents, module agents, and integration agents start in parallel, mocking anything not yet live. The secure core is never touched by app or surface code — those lanes call capabilities through the gateway, hold no credentials, and never read the canonical store. If human developers join later, the same boundary governs them unchanged.
