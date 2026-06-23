# Environment variable inventory — Ring 0

The consolidated inventory of every environment variable Ring 0 needs, gathered
from each module, grouped by service. **Names only.** No value appears here.

Naming convention: `clss.<app>.<env>.<purpose>`. The `<env>` segment is `dev`
below; staging and prod use `clss.<app>.staging.*` / `clss.<app>.prod.*`. Each
service's `config.py` is the single place that switches the resolved
environment.

> Values are placed in Infisical by the founder and never committed to code,
> config, logs, error messages, or chat. A service reads each value by the name
> below and reports any missing name on startup by name only. The same key
> material may back more than one name (for example the JWT public key and the
> database URL); names are kept per-service so ownership and rotation stay
> auditable.

---

## identity (`spine/identity`)

| Name | Purpose |
|------|---------|
| `clss.identity.dev.supabase_url` | Supabase project URL for the identity service. |
| `clss.identity.dev.supabase_service_key` | Supabase service-role key (vault access; identity only). |
| `clss.identity.dev.supabase_anon_key` | Supabase anon key for the Auth client. |
| `clss.identity.dev.database_url` | Postgres connection string (vault + platform). |
| `clss.identity.dev.jwt_private_key` | RS256 private signing key — identity only, never distributed. |
| `clss.identity.dev.jwt_public_key` | RS256 public key (the value distributed to gateway + event-store). |
| `clss.identity.dev.redis_url` | Redis for sessions, OTP, and rate-limit. |

## gateway (`spine/gateway`)

| Name | Purpose |
|------|---------|
| `clss.gateway.dev.jwt_public_key` | RS256 public key to verify identity tokens. |
| `clss.gateway.dev.identity_introspect_url` | Identity token-introspection endpoint. |
| `clss.gateway.dev.identity_base_url` | Identity service base URL (upstream). |
| `clss.gateway.dev.event_store_base_url` | Event-store base URL (upstream). |
| `clss.gateway.dev.database_url` | Postgres connection for the immutable audit sink. |
| `clss.gateway.dev.track1_router_url` | Track 1 external LLM router endpoint (Ring 1). |
| `clss.gateway.dev.track2_endpoint_url` | Track 2 proprietary / edge endpoint (reserved slot, Ring 2). |

## event-store (`spine/event-store`)

| Name | Purpose |
|------|---------|
| `clss.eventstore.dev.database_url` | Postgres connection (append-only `platform.events`). |
| `clss.eventstore.dev.supabase_url` | Supabase project URL for the event store. |
| `clss.eventstore.dev.supabase_service_key` | Supabase service-role key (service-role-mediated writes/reads). |
| `clss.eventstore.dev.jwt_public_key` | RS256 public key to verify identity tokens. |
| `clss.eventstore.dev.identity_consent_check_url` | Identity consent-check endpoint for the gated read path. |

## database / migrations (`db`)

| Name | Purpose |
|------|---------|
| `clss.school.dev.database_url` | Postgres connection string used to apply the canonical migrations. |

## web surface (`surfaces/web`)

| Name | Purpose |
|------|---------|
| `NEXT_PUBLIC_CLSS_WEB_PROD_GATEWAY_URL` | Public gateway base URL the browser calls (RBAC+ABAC at the wall). |
| `CLSS_WEB_PROD_GATEWAY_TOKEN` | Server-side gateway token for the web surface's privileged calls. |

> The web surface holds no other credential and never touches the event store or
> PII vault directly. Until the gateway is provisioned, `surfaces/web/lib/runtime.ts`
> gates the live path and the app degrades to its mock layer behind the same
> interface.

## AI fabric — Vidya / LLM providers (`spine/ai-fabric`, Slice 1+)

All LLM provider keys are **Track 1** and are reached only through the gateway →
AI fabric. They are read by name at the call site, never hardcoded; absence
degrades to a deterministic refusal (`GenerateResult.provider_available = false`),
never a fabricated answer.

| Name | Purpose |
|------|---------|
| `clss.aifabric.dev.gemini_api_key` | Gemini provider key. Backs **Vidya speech-to-speech** (REST pipeline: `gemini-2.5-flash` understands + replies, `gemini-2.5-flash-preview-tts` speaks — the realtime Live API is used instead when the tier exposes it) and Gemini text generation. Read SERVER-SIDE ONLY; never sent to the browser. Track 1; routed through the gateway behind the permission ladder, the confidence gate, and child-safety on every free-text surface. See `docs/VOICE.md`. |
| `clss.aifabric.dev.track1_provider_key` | Generic Track 1 provider key (alternate/secondary provider). |
| `clss.aifabric.dev.track1_router_url` | Track 1 router endpoint. |
| `clss.aifabric.dev.track2_endpoint_url` | Track 2 proprietary / edge endpoint (reserved slot). |
| `clss.aifabric.dev.track2_endpoint_key` | Track 2 endpoint key (reserved slot). |
| `clss.aifabric.dev.tracing_url` | LLM-observability (cost/latency/quality) collector endpoint. |
| `clss.aifabric.dev.tracing_key` | Observability collector key. |

> Vidya speech-to-speech runs the Gemini Live native-audio capability as a
> governed, least-privilege capability in the registry. The resolved local env
> name is `CLSS_AIFABRIC_DEV_GEMINI_API_KEY`. The founder places the value in
> Infisical (or a local, uncommitted shell export for dev); the value never
> appears in code, config, logs, or chat. Rotate immediately on any exposure.

---

## Provisioning-time note

- The Supabase database URL points all three spine services and the migration
  runner at the same Postgres; per-service names are kept for audit.
- The RS256 public key value is the same across the gateway and event-store
  names; only identity holds the private key.
- The unsigned dev-token path exists only for local contract testing with no key
  configured and is rejected the moment a real public key is present; it must
  never reach staging or prod.

See `ops/PROVISIONING.md` for what each resource is and the setup steps.
