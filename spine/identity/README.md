# Classess Identity service (Ring 0)

Canonical identity, app membership and scope, and consent. This service is the
single secure core component that holds PII. It mirrors the identity contract at
`contracts/src/openapi/identity.ts` and the canonical tables in `db/migrations`
(`vault.users`, `platform.app_memberships`, `platform.consents`).

## Why PII lives only here

Security invariants 1 and 2: the `canonical_uuid` is an opaque, random UUID
(`gen_random_uuid` / `uuid4`) that maps to a person ONLY inside the PII vault
(`vault.users`). No behavioral store carries PII. Deleting a vault row severs
identity while de-identified events remain unlinkable. No response model in this
service returns PII; the only thing that leaves the vault is the opaque
`canonical_uuid`.

The vault (`vault` schema) and the platform-canonical tables (`platform`
schema) are never joined by a SQL foreign key. The link is the shared opaque
value only.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/identity/auth/otp/start` | Begin phone-OTP (Supabase Auth mechanism). |
| POST | `/v1/identity/auth/otp/verify` | Verify OTP, mint a gateway-verifiable token. |
| POST | `/v1/identity/auth/token/introspect` | Verify a token; used by the gateway. |
| GET | `/v1/identity/memberships/resolve` | Active, time-bound memberships + scope (RBAC/ABAC inputs). |
| POST | `/v1/identity/consent/check` | Consent + purpose satisfied for a scope (INVARIANT 6). |
| POST | `/v1/identity/consent/grant` | Capture a consent grant. |
| POST | `/v1/identity/internal/users` | Privileged: issue a canonical user; returns the opaque id only. |
| GET | `/healthz` | Liveness + which store backend is active. |

## Tokens

The identity service MINTS gateway-verifiable JWTs with the PRIVATE key
(RS256). The gateway verifies with the PUBLIC key only. Claims carry the opaque
`canonical_uuid`, the `app`, and the membership list — never PII.

## Graceful degradation

The service imports and starts even when nothing is wired:

- No `clss.identity.dev.database_url` (or `asyncpg` missing): an in-memory,
  clearly-labelled, non-durable store is used so the API is fully exercisable.
- No `clss.identity.dev.jwt_private_key`: a loudly-logged unsigned DEV token is
  issued for local contract testing only. It must never be accepted in
  staging/prod. Set the key for real tokens.
- No `clss.identity.dev.supabase_url`: the OTP path runs a local dev challenge;
  in production, OTP dispatch and verification are delegated to Supabase Auth.

Missing config is reported on startup by env var NAME only — never a value.

## Environment variables (names only; values via Infisical)

All read from `CLSS_IDENTITY_DEV_*` (the shell-safe form of the dotted name).

- `clss.identity.dev.supabase_url`
- `clss.identity.dev.supabase_service_key`
- `clss.identity.dev.supabase_anon_key`
- `clss.identity.dev.database_url`
- `clss.identity.dev.jwt_private_key`  (PEM, RS256 — secret)
- `clss.identity.dev.jwt_public_key`   (PEM — also given to the gateway)
- `clss.identity.dev.redis_url`

## Run locally

```
# from spine/identity
uvicorn app.main:app --reload --port 8001
```

OpenAPI docs at `http://localhost:8001/docs`.
