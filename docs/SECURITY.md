# Security — the twelve invariants and how Ring 0 honors each

These twelve invariants are checkable, and Ring 0 is not done until every one
holds. This document restates each and cites where and how this build honors it.
It is the Ring 0 verification checklist.

---

### 1. PII is vaulted and segregated

PII lives in a separate, more-restricted store; the event store, profile, graph,
and feature store carry only the opaque `canonical_uuid` and behavioral data.

- `db/migrations/0001_extensions.sql` creates three schemas: `vault` (PII),
  `platform` (behavioral), `audit`.
- `db/migrations/0002_pii_vault.sql` defines `vault.users` as the only place PII
  lives; `db/migrations/0003_memberships_consent.sql` and `0004_events.sql` key
  every platform row by the opaque `canonical_uuid` alone — no PII columns.
- `spine/identity` is the sole service with a PII model; `spine/event-store`
  rejects PII keys in event payloads (`spine/event-store/app/verify.py`).

### 2. The canonical UUID is opaque

A random id, never derived from PII; deleting the vault row severs the link and
leaves aggregate behavior unlinkable.

- `vault.users.canonical_uuid` is a `gen_random_uuid()` primary key
  (`db/migrations/0002_pii_vault.sql`); identity generates it with `uuid4`, never
  from PII (`spine/identity/app/store.py`).
- There is deliberately no SQL foreign key across the vault->platform boundary
  (`db/migrations/0003_memberships_consent.sql`), so a vault delete severs
  identity while events remain.

### 3. Every call passes the gateway

No service is reachable unauthenticated; RBAC + ABAC are enforced at the wall.

- `spine/gateway` verifies the token, runs a deny-by-default RBAC+ABAC engine
  (`spine/gateway/app/policy.py`), and routes only on an explicit allow
  (`spine/gateway/app/routing.py`, `main.py`); an unknown operation is not
  routable.
- The three OpenAPI specs all require the bearer scheme
  (`contracts/src/openapi/*`).
- At the data layer, RLS is forced deny-all on every table
  (`db/migrations/0007_rls.sql`) and only the gateway operates as the service
  role; nothing else can reach the store.

### 4. Secrets are environment-only

Env vars exclusively, never in code, config, logs, or errors; named
`clss.<app>.<env>.<purpose>`.

- Every service reads secrets by env var NAME via its `config.py`
  (`spine/*/app/config.py`); no secret value is hardcoded.
- The web surface declares gateway env var names in `surfaces/web/lib/runtime.ts`
  and reads them from the environment.
- The full inventory (names only) is `ops/ENV.md`; values are placed in Infisical
  by the founder and never committed.

### 5. The event contract is immutable and append-only from line one

Clean attributed events; never mutated or deleted in place.

- `platform.events` carries `BEFORE UPDATE` and `BEFORE DELETE` triggers calling
  `platform.deny_mutation()`, which raises an exception
  (`db/migrations/0004_events.sql`); the triggers propagate to all partitions.
- `spine/event-store` exposes no update or delete endpoint and inserts only
  (`spine/event-store/app/main.py`, `store.py`).
- The event-store OpenAPI intentionally omits any update/delete operation
  (`contracts/src/openapi/event-store.ts`).

### 6. Consent is a primitive

Captured at identity, stamped on every event, gating every cross-context read.

- `platform.consents` (`db/migrations/0003_memberships_consent.sql`) is captured
  by `spine/identity` (`consent/grant`, `consent/check`).
- The write path stamps `consent_ref` at emit time; the read path
  `platform.read_events(canonical_uuid, purpose)` returns rows only under an
  active consent for that purpose, otherwise an empty set
  (`db/migrations/0006_governed_views.sql`), mirrored by `spine/event-store`.
- The gateway requires `X-Consent-Purpose` for cross-context reads
  (`spine/gateway/app/policy.py`).

### 7. Generate-and-verify

No generated content is served unverified; a confidence gate refuses anything
that fails verification. (The substrate is Ring 1; the contract is defined now.)

- The `Verification` and confidence-gate contracts are defined in
  `contracts/src/events` for Ring 1 to fill.
- The web surface carries the gate today in `surfaces/web/app/_components/respond.ts`
  (the local stand-in for the live generate-and-verify turn responder), to be
  swapped for a gateway call when the AI fabric is wired.

### 8. Permission ladder on any agent action

Recommend -> Prepare -> Execute-with-permission -> Safe-automatic. Anything
consequential requires explicit human approval; agents hold no credentials.

- `PermissionRung` is a defined contract (`contracts/src/events`).
- The web surface renders recommendations at Prepare-not-Execute posture: each
  item in `/proactive` shows evidence, confidence, owner, due date, and
  consequence, with an Approve/Adjust/Decline control that never auto-fires
  (`surfaces/web/app/_components/RecommendationItem.tsx`).

### 9. Audit is immutable; privileged actions are break-glass

Every privileged action is recorded and reviewable.

- `spine/gateway` writes an immutable audit record for every decision, allow and
  deny (`spine/gateway/app/audit.py`).
- `audit.audit_log` carries the same `deny_mutation` immutability triggers as
  events (`db/migrations/0005_audit.sql`), forced deny-all under RLS
  (`0007_rls.sql`).

### 10. Encryption in transit and at rest; tenant isolation

- `db/migrations/0002_pii_vault.sql` documents encryption-at-rest and
  access-logging intent per PII column; Supabase provides TLS in transit and
  at-rest encryption (provisioning in `ops/PROVISIONING.md`).
- Logical separation per institution is carried by the membership `scope` and
  enforced by the gateway ABAC scope-containment check
  (`spine/gateway/app/policy.py`); deepened to full multi-tenancy in Ring 2.

### 11. Two tracks are never conflated

Track 1 (external LLM routing) and Track 2 (proprietary / edge) are separate in
gateway config; the Track 2 slot exists from the start and is filled later.

- `spine/gateway/app/config.py` keeps `TrackConfig.track1` and
  `TrackConfig.track2` as two structurally separate sections; both are inspectable
  at `GET /v1/tracks`. Track 2 is a reserved slot, no re-architecture needed to
  fill it.

### 12. Confidentiality discipline

No codenames, personal names, board lock-in language, or placeholder text in any
developer- or team-facing artifact; the confidential orchestrator is never named.

- Every artifact in this build was written under the confidentiality scrub: mock
  data is fictional and generic (for example Student A, Class 10-B), no real
  pricing appears (the literal placeholder is used where a price would go), and
  there are no codenames or personal names anywhere in `contracts/`,
  `packages/design-system`, `surfaces/web`, `spine/`, `db/`, or `docs/`.
