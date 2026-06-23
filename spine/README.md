# Spine — the secure core (Ring 0)

Three Ring 0 FastAPI services. Founder + Claude Code only; never handed to the
developer lanes. Each is a typed, production-shaped service that mirrors the
contracts in `contracts/src` and the canonical tables in `db/migrations`.

```
spine/
  identity/      # canonical user (PII vault), AppMembership, RBAC/ABAC, consent
  gateway/       # THE WALL: token verify, RBAC+ABAC, validate, audit, route
  event-store/   # immutable append-only write-path + governed, consented read
```

## The boundary

The PII vault lives in `identity` and nowhere else. It is the only place the
opaque, random `canonical_uuid` maps to a person (INVARIANT 1, 2). Everything
that crosses any service boundary carries the opaque `canonical_uuid` and
non-identifying authorization inputs only. Deleting a vault row severs identity
while de-identified events remain unlinkable.

## The three wires

1. **Identity token** — `identity` mints a gateway-verifiable JWT (RS256). The
   private signing key lives only in `identity`; the gateway and the event store
   hold only the public key. Claims carry the opaque `canonical_uuid`, the app,
   and the membership list — never PII.
2. **The gateway** — every call passes the wall (INVARIANT 3). It verifies the
   token, enforces RBAC + ABAC (deny by default), validates the request against
   the target capability contract, writes an immutable audit record (INVARIANT
   9), then routes. No capability is reachable except through the gateway.
3. **The event seam** — modules emit attributed events up into the immutable
   `event-store` (firehose) and read governed, consent + purpose-gated scoped
   views back down (faucet). No bulk read of the canonical store exists.

The circuit: identity -> gateway -> capability -> event -> (intelligence,
Ring 1) -> recommend -> approve -> execute -> outcome -> learn.

## The two tracks (INVARIANT 11)

The gateway config keeps Track 1 (external LLM routing) and Track 2
(proprietary / edge models) in two structurally separate sections
(`spine/gateway/app/config.py` -> `TrackConfig.track1`, `TrackConfig.track2`).
Track 2 is a reserved slot that exists from line one and is filled in Ring 2
with no re-architecture. Inspect both at `GET /v1/tracks` on the gateway.

## Security invariants realized here

- **PII vaulted + segregated** — `identity` holds the vault; no other service
  has a PII model; `event-store` rejects PII keys in payloads.
- **Opaque canonical_uuid** — generated with `gen_random_uuid` / `uuid4`, never
  derived from PII.
- **Every call passes the gateway** — deny-by-default policy engine; no rule,
  no access.
- **Secrets are environment-only** — every secret is read by env var NAME
  (`clss.<app>.<env>.<purpose>`); no value is hardcoded, invented, or logged.
- **Immutable, append-only events** — the `event-store` write-path is INSERT
  only; no update/delete endpoint exists; the DB trigger is the hard backstop.
- **Consent is a primitive** — captured in `identity`, stamped on every event,
  and gates every read through `platform.read_events`.
- **Audit is immutable** — every gateway decision (allow or deny) is recorded.

## Local run

Each service is an independent FastAPI app. Suggested ports:

```
# identity
cd spine/identity      && uvicorn app.main:app --reload --port 8001
# event-store
cd spine/event-store   && uvicorn app.main:app --reload --port 8002
# gateway (routes to the two above)
cd spine/gateway       && uvicorn app.main:app --reload --port 8000
```

With nothing configured, all three start in a clearly-labelled DEGRADED mode
(in-memory stores, logger audit sink, unsigned dev tokens) so the contracts are
fully exercisable without a live Supabase. Provide the env vars below to move to
the production path. Missing config is reported on startup by env var NAME only.

## Env var inventory (names only; values via Infisical)

Each dotted name is read from the shell-safe `CLSS_<APP>_DEV_*` form.

### identity (`CLSS_IDENTITY_DEV_*`)
- `clss.identity.dev.supabase_url`
- `clss.identity.dev.supabase_service_key`
- `clss.identity.dev.supabase_anon_key`
- `clss.identity.dev.database_url`
- `clss.identity.dev.jwt_private_key`  (secret — signing key, identity only)
- `clss.identity.dev.jwt_public_key`   (shared with gateway + event-store)
- `clss.identity.dev.redis_url`

### gateway (`CLSS_GATEWAY_DEV_*`)
- `clss.gateway.dev.jwt_public_key`
- `clss.gateway.dev.identity_introspect_url`
- `clss.gateway.dev.identity_base_url`
- `clss.gateway.dev.event_store_base_url`
- `clss.gateway.dev.database_url`  (audit sink)
- `clss.gateway.dev.track1_router_url`  (Track 1)
- `clss.gateway.dev.track2_endpoint_url`  (Track 2 — reserved)

### event-store (`CLSS_EVENTSTORE_DEV_*`)
- `clss.eventstore.dev.database_url`
- `clss.eventstore.dev.supabase_url`
- `clss.eventstore.dev.supabase_service_key`
- `clss.eventstore.dev.jwt_public_key`
- `clss.eventstore.dev.identity_consent_check_url`

The same key may back more than one service (e.g. the JWT public key is given to
the gateway and the event store; the database URL points all three at the same
Supabase Postgres). Names are per-service so ownership and rotation stay
auditable.

## Note on staging/prod env naming

The `dev` segment in each name reflects the current environment. Staging and
prod use `clss.<app>.staging.*` / `clss.<app>.prod.*`; the `env_prefix` in each
service's `config.py` is the single place to switch the resolved environment.
