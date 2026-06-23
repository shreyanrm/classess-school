# Classess School - Ring 0 canonical / platform DB substrate

These migrations stand up the secure core data layer: the PII vault, the
behavioral/canonical platform store, and the immutable audit log. They encode
the security model structurally, not by convention.

## The segregation rule (the whole point)

The PII vault is **physically segregated** from the behavioral event store, at
the schema level:

- `vault` holds PII (`vault.users`). It is the **only** place the opaque
  `canonical_uuid` maps to a real person. The `canonical_uuid` is a random
  UUID v4 (`gen_random_uuid`); it is **never** derived from PII.
- `platform` holds behavioral / canonical data (`app_memberships`, `consents`,
  `events`). Every row carries **only** the opaque `canonical_uuid` and
  behavioral data - **never** PII.
- There is **deliberately no SQL foreign key** across the `vault` -> `platform`
  boundary. The link is the shared opaque value alone. Deleting the
  `vault.users` row **severs identity**: the de-identified events remain and
  are **unlinkable** to a person. DPDP-clean by construction, not by cleanup.

`audit` holds the immutable record of privileged / break-glass actions, also
with opaque references only.

## Schemas

| Schema     | Contents                                   | Posture                          |
|------------|--------------------------------------------|----------------------------------|
| `vault`    | `users` (PII)                              | Most restricted. RLS deny-all + privileges revoked from client roles. |
| `platform` | `app_memberships`, `consents`, `events`    | Behavioral plane. RLS deny-all; reads via governed function. |
| `audit`    | `audit_log`                                | Immutable append-only. RLS deny-all. |

## Migration files (apply in order)

| File | What it does |
|------|--------------|
| `0001_extensions.sql`        | Extensions (`pgcrypto`, `vector`, `btree_gist`); schemas `vault`, `platform`, `audit`. |
| `0002_pii_vault.sql`         | `vault.users` - opaque `canonical_uuid` PK, PII columns, encryption/access-log intent. |
| `0003_memberships_consent.sql` | `platform.app_memberships` and `platform.consents` (time-bound, opaque-keyed). |
| `0004_events.sql`            | `platform.events` - append-only, immutable (trigger), monthly range partitions. |
| `0005_audit.sql`             | `audit.audit_log` - immutable append-only. |
| `0006_governed_views.sql`    | `platform.read_events()` - consent+purpose-gated read path. |
| `0007_rls.sql`               | RLS enable + force + restrictive default-deny on all tables. |

## How to apply

### Supabase CLI

Place these files in `supabase/migrations/` (or symlink) and run:

```sh
supabase db push
```

Or, with the project linked, apply them as the standard ordered migration set.

### psql

```sh
psql "$DATABASE_URL" \
  -f migrations/0001_extensions.sql \
  -f migrations/0002_pii_vault.sql \
  -f migrations/0003_memberships_consent.sql \
  -f migrations/0004_events.sql \
  -f migrations/0005_audit.sql \
  -f migrations/0006_governed_views.sql \
  -f migrations/0007_rls.sql
```

`DATABASE_URL` resolves from the environment only (Infisical). Env var name:
`clss.school.<env>.database_url`. Never hardcode the connection string.

> Do not run installers/build here - only apply migrations. They are idempotent
> (`IF NOT EXISTS`, `CREATE OR REPLACE`, guarded `DO` blocks) and safe to re-run.

## Immutability guarantees

- `platform.events` and `audit.audit_log` each carry `BEFORE UPDATE` and
  `BEFORE DELETE` row triggers calling `platform.deny_mutation()`, which
  `RAISE EXCEPTION`s. Rows can only be inserted; never changed or removed in
  place. On the partitioned `events` parent, the row triggers propagate to all
  current and future partitions automatically.
- This is enforcement, not advice: an `UPDATE` or `DELETE` against these tables
  fails with `restrict_violation`.

## How reads work (consent + purpose gate)

Never bulk-select `platform.events`. Read through:

```sql
SELECT * FROM platform.read_events('<canonical_uuid>'::uuid, '<purpose>');
```

It returns rows **only** when an active consent
(`platform.consents.revoked_at IS NULL`) exists for that `(canonical_uuid,
purpose)` **and** the event was emitted under that same purpose. Otherwise it
returns an empty set (never an error - existence is not leaked). RLS (the
identity gate) and this function (the purpose gate) are layered: both apply.

`platform.satisfied_purposes('<canonical_uuid>')` lists a person's active
purposes without exposing any event contents.

## How to add a monthly partition

Add the next month ahead of time (ideally automated via a scheduled job):

```sql
CREATE TABLE IF NOT EXISTS platform.events_y2026m08
  PARTITION OF platform.events
  FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');
```

A `platform.events_default` catch-all partition exists so inserts never fail
for a missing month; migrate rows out of it once the proper monthly partition
is created. Shipped partitions: `2026-06`, `2026-07`, plus the default.

## RLS posture

- RLS is `ENABLE`d and `FORCE`d on every base table, with restrictive
  `USING (false)` deny-all policies. No permissive policies exist for
  `anon`/`authenticated`, so direct client access is denied.
- All legitimate access is mediated by the **gateway** running as the Supabase
  **service role** (which bypasses RLS by design), under RBAC + ABAC enforced
  at the wall. The `vault` schema is hardest: client-role table privileges and
  schema usage are revoked outright, in addition to RLS.

## Rollback story

Migrations create only new schemas/objects and add no destructive changes to
pre-existing data, so rollback is a clean teardown of what was created:

```sql
-- Reverse order. CASCADE drops dependent partitions, triggers, policies, fns.
DROP SCHEMA IF EXISTS audit    CASCADE;
DROP SCHEMA IF EXISTS platform CASCADE;
DROP SCHEMA IF EXISTS vault    CASCADE;
-- Extensions are left in place (shared, harmless). Drop explicitly if required:
-- DROP EXTENSION IF EXISTS vector;  DROP EXTENSION IF EXISTS btree_gist;
-- (pgcrypto is commonly relied on elsewhere; drop only if you are sure.)
```

For a managed-migration workflow (Supabase CLI), prefer a paired down-migration
per file rather than the blanket schema drop above. The blanket drop is the
fresh-environment reset path; do not run it against data you intend to keep.
