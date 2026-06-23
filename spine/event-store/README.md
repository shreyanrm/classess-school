# Classess Event Store service (Ring 0)

The immutable, append-only behavioral event store and its governed read path.
Mirrors `contracts/src/openapi/event-store.ts`, the event contract in
`contracts/src/events/*`, and the canonical tables + governed function in
`db/migrations` (`platform.events`, `platform.read_events`).

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/v1/event-store/events` | Append an attributed event (INVARIANT 5). |
| GET | `/v1/event-store/events` | Governed, consent + purpose-gated read (INVARIANT 6). |
| GET | `/v1/event-store/events/{event_id}` | Governed single-event read. |
| GET | `/healthz` | Liveness + active store backend. |

There is deliberately **no** update and **no** delete endpoint.

## Immutability (INVARIANT 5)

The write-path is INSERT-only. The Postgres adapter never issues UPDATE or
DELETE; the migrations add a `BEFORE UPDATE/DELETE` trigger
(`platform.deny_mutation`) and INSERT-only grants as the hard enforcement.
`emit_event` validates the input against the event contract (the discriminated
union of typed payloads, including the attempt independent-vs-supported
coherence rule), stamps `event_id` / `recorded_at` / `schema_version`, and
appends.

## Governed reads (INVARIANT 6)

Reads return **only** through `platform.read_events(canonical_uuid, purpose)`.
That function returns rows only when an active consent for `(person, purpose)`
exists AND the event's own stamped purpose matches. Without a satisfied consent
it returns an **empty set** — never the rows, never an error that leaks
existence. There is no bulk-select path over `platform.events` in this service.
A single-event read that the gate would withhold returns `404`, not `403`, so
"not found" and "not visible" are indistinguishable.

## PII segregation (INVARIANT 1, 2)

Every stored row carries the opaque `canonical_uuid` only. `emit_event` rejects
any payload that carries top-level PII keys (`phone`, `name`, `dob`, `email`,
...) with a `422` that names the offending keys, never their values — a
second wall on top of the DB CHECK intent.

## Schema-version normalization

The DB stores `schema_version` as an integer (default `1`); the event contract
envelope uses the string `"v1"`. The data layer normalizes `1` <-> `"v1"` at
the boundary so the API always speaks the contract.

## Graceful degradation

- No `clss.eventstore.dev.database_url` (or `asyncpg` missing): a
  clearly-labelled, non-durable, **append-only** in-memory log is used. It
  enforces the same discipline — no mutation API, and reads still pass the
  consent + purpose gate (seed a consent via the dev seam to exercise reads).
- No `clss.eventstore.dev.jwt_public_key`: a clearly-marked unsigned dev token
  is accepted for local contract testing only; with a real key present, unsigned
  tokens are rejected.

## Environment variables (names only; values via Infisical)

Read from `CLSS_EVENTSTORE_DEV_*`.

- `clss.eventstore.dev.database_url`
- `clss.eventstore.dev.supabase_url`
- `clss.eventstore.dev.supabase_service_key`
- `clss.eventstore.dev.jwt_public_key`  (PEM — verify only)
- `clss.eventstore.dev.identity_consent_check_url`

## Run locally

```
# from spine/event-store
uvicorn app.main:app --reload --port 8002
```

OpenAPI docs at `http://localhost:8002/docs`.
