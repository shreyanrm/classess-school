# Gateway hardening: the wall enforces every call

This document supplements the gateway README. It covers the hardening added so
that "every call passes the wall" holds for the FEATURE / capability modules,
with rate limiting and request schema validation enforced before routing.

Note for maintainers: this file is additive. Fold its contents into the main
`README.md` at your convenience and link to it from the gateway overview.

## What the wall enforces, in order

Every request runs through a single pipeline (`app/wall.py :: Wall.admit`). The
first failing gate fails closed; every decision -- allow or deny -- is audited.

1. Route exists (capability is registered) -- unknown routes fail closed.
2. Authentication -- a valid bearer token resolves to a `Principal`
   (opaque `canonical_uuid` + roles + attributes). No token / bad token is
   rejected. With no token verifier wired, every token is invalid (degrades
   closed, never open).
3. Rate limit -- per `principal + route`, config-driven (`app/ratelimit.py`).
4. Request schema validation -- per-route schema, before routing
   (`app/validation.py`). Malformed bodies are rejected with field PATHS only,
   never values.
5. RBAC -- the principal's role must be permitted for the capability.
6. ABAC -- an attribute predicate (e.g. same-institution) must hold.
7. Consent gate -- a cross-context read requires a granted consent scope.
8. Permission ladder -- consequential actions (e.g. exports) require a human
   approval token and never auto-fire.
9. Child-safety -- every declared free-text field is screened before forward.
10. Audit -- an immutable, append-only event carrying only the opaque
    `canonical_uuid` (never PII) is recorded for the allow or the deny.

## Rate limiting (`app/ratelimit.py`)

- Algorithms: `token_bucket` (burst-tolerant) and `fixed_window` (boundary
  reset), selectable per route via config.
- Keyed by `principal + route`. Principal is an opaque id, never PII.
- Pluggable storage via `RateLimitStore`. `InMemoryRateLimitStore` is the
  default and the degrade target. `RedisRateLimitStore` wraps a Redis client
  and degrades GRACEFULLY to in-memory when no client is configured or the
  backend errors -- the request path never fails on infrastructure.
- Config-driven via `RateLimiter.from_config({...})`.

Example config:

```json
{
  "default": {"limit": 120, "window_seconds": 60, "algorithm": "token_bucket"},
  "routes": {
    "intelligence-views.read": {"limit": 30, "window_seconds": 60},
    "feature-store.export": {"limit": 5, "window_seconds": 60, "algorithm": "fixed_window"}
  }
}
```

## Request schema validation (`app/validation.py`)

- Per-route schemas declared via `RequestSchema` / `FieldSpec`, registered in a
  `SchemaRegistry` and validated at the wall before any routing.
- Strict by default: undeclared fields are rejected, so the wall never forwards
  a field a module did not declare.
- Supports required/optional, primitive types, bounds, enums, regex, nested
  objects and typed arrays.
- Free-text fields are flagged (`free_text=True`) so the wall routes them
  through the child-safety screen. Errors reference field paths only.

## Routable capabilities (`app/capabilities.py`)

`build_default_registry()` registers every feature module as a routable
capability behind the wall:

    institution, scheduling, coursework, learning, content, learner-record,
    communication, intelligence-views, attendance, planning, classroom,
    teacher-growth, integration, feature-store

Each module exposes a `read` capability (and `write` / `export` where it
applies). Reads are gated by RBAC + ABAC (and consent on cross-context reads);
exports are consequential and require human approval. A module's HTTP handler
stays thin -- the wall is what enforces access.

To compose with the gateway's existing route map, call
`build_default_registry()` and merge / register its `Capability` entries into
the live registry, then construct a `Wall` with your real `TokenVerifier`,
`ConsentChecker`, `ChildSafetyScreen` and `AuditSink`. Where a collaborator is
not supplied, the wall uses a fail-closed default (deny-all auth, block-all
child-safety, in-memory append-only audit).

## Configuration (ENV-only, server-side)

No secret is hardcoded. The Redis connection string is read from an
environment variable and handed to `RedisRateLimitStore` by the caller:

- `clss.gateway.<env>.redis_url` -- Redis connection URL for rate-limit state.
  Absent -> the limiter degrades to in-memory. Never expose as a
  `NEXT_PUBLIC_*` value; this is server-side only.

## Tests

Run from the gateway root with no network or database:

```
pytest tests/test_ratelimit.py tests/test_validation.py tests/test_wall_capabilities.py
```

Coverage:

- rate limit triggers and resets (token bucket + fixed window), per-principal
  and per-route isolation, Redis degrade-to-memory.
- schema validation rejects a malformed request before routing.
- a feature-module route is unreachable without a valid token + satisfied
  policy, and every decision is audited (append-only, opaque id only).
