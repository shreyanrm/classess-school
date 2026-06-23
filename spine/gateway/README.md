# Classess Gateway service — THE WALL (Ring 0)

The single wall every call passes (INVARIANT 3). It verifies the identity
token, enforces RBAC + ABAC (deny by default), validates the request, writes an
immutable audit record, and routes to the target capability. No capability is
reachable except through here. Mirrors `contracts/src/openapi/gateway.ts`.

## The sequence on every routed call

1. Verify the identity token (PUBLIC key, RS256 — the gateway never holds the
   private key; deny by default if absent/invalid).
2. Resolve the operation in the explicit route map (`app/routing.py`). An
   operation not in the map is not routable.
3. Evaluate RBAC + ABAC against the caller's resolved memberships
   (`app/policy.py`). No matching rule means deny.
4. For cross-context reads, require the `X-Consent-Purpose` assertion
   (INVARIANT 6).
5. Write an immutable audit record for the outcome — allow or deny
   (INVARIANT 9, `app/audit.py`).
6. Only on allow: forward to the upstream capability and return its response.

## Deny by default

`PolicyEngine.baseline()` registers the explicit Ring 0 rules for the two
reachable capabilities (`identity`, `event-store`). Any operation without a rule
is denied. ABAC scope containment ensures a caller may only act within a scope a
membership covers — there is no global bypass, admins included.

## The two tracks (INVARIANT 11)

`app/config.py` holds `TrackConfig` with two distinct sections:

- `track1` — external LLM routing (LiteLLM, Ring 1). The gateway holds only the
  router endpoint name; provider keys live behind the router, never here.
- `track2` — proprietary / edge models. The slot exists now and is filled in
  Ring 2. Separate ownership, separate config. Filling it is a config change,
  not a re-architecture.

Inspect both at `GET /v1/tracks`.

## Graceful degradation

- No `clss.gateway.dev.jwt_public_key`: falls back to identity introspection at
  `clss.gateway.dev.identity_introspect_url`; with neither set, every call is
  denied (deny by default), naming the env var to set.
- No `clss.gateway.dev.database_url`: audit records are logged structurally (no
  PII) instead of stored durably, naming the env var to set. The wall never
  silently drops an audit.
- An upstream `*_base_url` that is unset returns a 503 naming the env var, never
  a crash.

## Environment variables (names only; values via Infisical)

Read from `CLSS_GATEWAY_DEV_*`.

- `clss.gateway.dev.jwt_public_key`  (PEM — verify only; never the private key)
- `clss.gateway.dev.identity_introspect_url`
- `clss.gateway.dev.identity_base_url`
- `clss.gateway.dev.event_store_base_url`
- `clss.gateway.dev.database_url`  (audit sink -> `platform.audit_log`)
- `clss.gateway.dev.track1_router_url`  (Track 1 — external LLM routing)
- `clss.gateway.dev.track2_endpoint_url`  (Track 2 — reserved slot)

## Run locally

```
# from spine/gateway
uvicorn app.main:app --reload --port 8000
```

OpenAPI docs at `http://localhost:8000/docs`.
