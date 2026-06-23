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
| POST | `/v1/identity/auth/sso/start` | Begin SSO via Google / Apple / Microsoft / institutional SAML. |
| POST | `/v1/identity/auth/sso/callback` | Complete SSO; auto-provisions ONE canonical identity on first signup. |
| POST | `/v1/identity/auth/token/introspect` | Verify a token; used by the gateway. |
| GET | `/v1/identity/memberships/resolve` | Active, time-bound memberships + scope (RBAC/ABAC inputs); folds in active grants. |
| POST | `/v1/identity/devices/register` | Register a device (opaque fingerprint; no PII). |
| GET | `/v1/identity/devices` | List a user's devices. |
| POST | `/v1/identity/devices/{device_id}/revoke` | Revoke a device. |
| POST | `/v1/identity/sessions/risk` | Assess a session's risk band from coarse signals (recommends step-up, never blocks). |
| GET | `/v1/identity/access-history` | Full access history for an identity. |
| POST | `/v1/identity/access-grants` | Create a delegated/temporary/substitute time-bound grant. |
| GET | `/v1/identity/access-grants` | List grants by grantee or grantor. |
| POST | `/v1/identity/access-grants/{grant_id}/revoke` | Revoke a grant immediately. |
| POST | `/v1/identity/consent/check` | Consent + purpose satisfied for a scope (INVARIANT 6). |
| POST | `/v1/identity/consent/grant` | Capture a consent grant. |
| POST | `/v1/identity/internal/users` | Privileged: issue a canonical user; returns the opaque id only. |
| GET | `/healthz` | Liveness + which store backend is active. |

## The single front door

Phone-OTP stays primary. Google / Apple / Microsoft and institutional SSO/SAML
are delegated federations: `auth/sso/start` builds the provider authorization
URL plus an anti-forgery `state`; `auth/sso/callback` validates the `state` and,
on first callback for a provider subject, AUTO-PROVISIONS one canonical identity
(one identity per human, established once, here). With no provider config the
start route returns a clearly-labelled local dev URL and the callback still
issues a token, so the contract is exercisable offline — no live network.

## Roles

The role model carries the institution's distinct control-surface roles:
`admin` (owner/principal), `teacher`, `student`, `parent`, plus `coordinator`,
`hod`, `examination`, `support`, and `it`. A role is an authorization input;
*where*/*for whom* is governed by ABAC scope.

## Delegated / temporary / substitute access

These are first-class TIME-BOUND grants. A grant for a grantee surfaces as a
membership (so the resolver and gateway treat it like any other) but ONLY inside
`[starts_at, expires_at]`, and is revocable immediately. Grants are never
open-ended (`expires_at` is required). This backs the substitution ladder's
Level 5 "external substitute — time-bound access, removed after".

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
- `clss.identity.dev.google_client_id`     (SSO — degrades cleanly when absent)
- `clss.identity.dev.apple_client_id`      (SSO — degrades cleanly when absent)
- `clss.identity.dev.microsoft_client_id`  (SSO — degrades cleanly when absent)
- `clss.identity.dev.saml_entity_id`       (institutional SSO — degrades cleanly)
- `clss.identity.dev.saml_sso_url`         (institutional IdP entry point)

## Run locally

```
# from spine/identity
uvicorn app.main:app --reload --port 8001
```

OpenAPI docs at `http://localhost:8001/docs`.
