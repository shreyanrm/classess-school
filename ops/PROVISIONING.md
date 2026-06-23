# Provisioning — Ring 0

What must be provisioned for Ring 0 to run on its production path, and the
reproducible steps to do it. Source code is complete and degrades gracefully
behind named env vars until these resources exist; nothing below requires a
re-architecture to fill.

> Secrets are environment-only. When a step produces a credential, the founder
> places it in Infisical under the name in `ops/ENV.md` — never into chat, code,
> config, or this file. This document records what was provisioned and how, by
> name only.

---

## 1. What must be provisioned

| Resource | Used by | Ring |
|----------|---------|------|
| Supabase project: Postgres + pgvector | `db`, `spine/event-store`, `spine/identity`, `spine/gateway` | 0 |
| Supabase Auth (phone-OTP first; Google / Apple) | `spine/identity` | 0 |
| Supabase Realtime | high-velocity tier (chat, threads, presence) | 0 base, used Ring 1+ |
| Supabase Storage + CDN | media, generated assets, scanned scripts | 0 base, used Ring 1+ |
| Redis | cache, sessions, OTP, rate-limit | 0 |
| Infisical project | every service's secrets | 0 |
| CI/CD from the GitHub org | the whole repo | 0 |
| LLM provider (routed via the gateway) | `spine/gateway` Track 1 | 1 |

The Track 2 (proprietary / edge) slot exists in gateway config from line one and
is provisioned in Ring 2; no action is needed for it in Ring 0.

---

## 2. Setup steps

### 2.1 Supabase project

1. Create the Supabase project. Record the project ref, the project URL, and the
   region in this file (no keys).
2. Enable the required Postgres extensions — `pgcrypto`, `vector` (pgvector),
   `btree_gist`. Migration `0001` enables them, so this is satisfied by applying
   the migrations on a project that permits those extensions.
3. Capture the connection details into Infisical under the names in `ops/ENV.md`:
   the project URL, the service-role key, the anon key, and the database URL.
4. Enable Supabase Auth with phone-OTP as the primary method; add Google and
   Apple providers.
5. Enable Realtime and Storage (used from Ring 1; provisioning them now keeps the
   base complete).

### 2.2 Apply the canonical migrations

Apply the seven migrations in order to the fresh project (full recipes in
`db/README.md`). The connection string resolves from the environment only:

```bash
psql "$DATABASE_URL" \
  -f db/migrations/0001_extensions.sql \
  -f db/migrations/0002_pii_vault.sql \
  -f db/migrations/0003_memberships_consent.sql \
  -f db/migrations/0004_events.sql \
  -f db/migrations/0005_audit.sql \
  -f db/migrations/0006_governed_views.sql \
  -f db/migrations/0007_rls.sql
```

The migrations are idempotent and ship the 2026-06 and 2026-07 event partitions
plus a default catch-all. Schedule a job to pre-create each next-month partition
ahead of ingest (template in `db/README.md`).

### 2.3 Redis

Provision a Redis instance (cache, sessions, OTP, rate-limit). Place its URL in
Infisical under the name in `ops/ENV.md`.

### 2.4 Token signing keys

Mint an RS256 key pair for identity tokens. The private key goes to Infisical
under the identity signing-key name (identity only); the matching public key
goes under the gateway and event-store public-key names so both can verify.
Per-service names keep rotation and audit clean. The unsigned dev-token path is
for local contract testing only and is rejected once a real public key is set.

### 2.5 Infisical and CI

1. Create the Infisical project and the `dev`, `staging`, `prod` environments.
2. Enter every name from `ops/ENV.md` with the founder-supplied value.
3. Wire CI/CD from the GitHub org to pull secrets from Infisical at build/deploy
   time; confirm no secret is ever printed to logs.

### 2.6 LLM provider (Ring 1)

When the AI fabric lands, provision the LLM provider and route it through the
gateway Track 1 config; the provider key is read by the gateway by name only.
Track 2 stays a reserved slot until Ring 2.

---

## 3. Verification after provisioning

- Migrations apply cleanly to the fresh project and the documented rollback
  tears them down.
- A user signs in via phone-OTP; a membership scopes access; consent is recorded
  and queryable.
- No route is reachable without a valid token and a satisfied RBAC/ABAC policy;
  every call is audited.
- A sample attributed event is emitted, stored immutably, and reads back only
  through the consent + purpose-gated view.
- Deleting a `vault.users` row leaves the corresponding events present and
  unlinkable to a person.
