# Data model and contracts

## Three store classes — and the line between them is the security model

### Canonical / platform (secure core — developers never touch directly)

Materialized in Ring 0:

- **PII vault** (separate, restricted): `canonical_uuid` (PK, random/opaque), phone, name, dob, other PII — encrypted, access-logged. The only place `canonical_uuid` maps to a person.
- `app_memberships`: `canonical_uuid`, app, role, scope, granted_at, revoked_at.
- `consents`: `canonical_uuid`, scope, purpose, age_tier, granted_by, granted_at, revoked_at.
- `events` (append-only, immutable, partitioned): `event_id`, `canonical_uuid` (opaque ref only), app, type, purpose, `consent_ref`, payload (jsonb), occurred_at, recorded_at.
- `audit_log` (immutable).
- **Derived projections** (built by replaying `events`, never authored directly — Ring 1+): `profiles`, `learner_graph`, `feature_store`.

### Operational (per capability module — Postgres + pgvector, behind the gateway)

Contract-defined now, materialized as each slice arrives: institution + hierarchy, ontology + prerequisite graph (pgvector), content metadata, timetable, attendance, coursework, gradebook, learner record (school-facing view), policies, consent records, audit. Each module owns its own tables. **Modules never share tables — only events.**

### High-velocity / ephemeral

Supabase Realtime (chat, AI threads, notifications, live session events, presence, leaderboards) · Redis (cache, sessions, OTP, rate-limit) · Supabase Storage + CDN (media, generated assets, scanned scripts).

> Firestore is the documented fallback for the very-high-velocity tier if a surface outgrows Supabase Realtime. Kept out of the base to keep it lean; add deliberately, not by default.

## The PII rule (schema-level)

The PII vault is physically separate from the behavioral event store. Every behavioral row is keyed by `canonical_uuid` with no PII present. Deleting the vault row severs identity; de-identified aggregate behavior remains and is unlinkable. DPDP-clean by construction, not by cleanup.

## The `/contracts` package — single source of truth

Written before any parallel work. Everything binds to it.

- `events/` — event + evidence schemas, versioned, immutable. Defines the **attempt event**, the **independent-vs-supported flag**, the **mastery weighting** (Performance × Reliability × Independence × Difficulty × Recency × Consistency), and the **ten gap types** (prerequisite, conceptual, procedural, application, retention, language, accuracy, speed, confidence, support-dependency).
- `openapi/` — per-capability API specs. The only thing surfaces and developers bind to.
- `db/` — canonical DB schemas + migrations.
- `tokens/` — v4 design tokens. **Regenerate the v4 brand skill before building UI; do not apply the stale v3 skill.**
