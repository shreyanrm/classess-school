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
| `clss.gateway.dev.jwt_public_key` | RS256 public key to verify identity tokens (gateway + the in-process Wall). Maps to `CLSS_GATEWAY_DEV_JWT_PUBLIC_KEY`. Unset ⇒ DEV-UNSIGNED tokens are accepted (local/dev only); set the key and signed RS256 verification turns on (in `backend/wall_auth.py` too) and dev tokens are rejected. Generate a keypair with `scripts/gen-jwt-keypair.sh` — identity keeps the private key, the gateway + event-store get the public key. Never commit a key value. |
| `clss.gateway.dev.identity_introspect_url` | Identity token-introspection endpoint (fallback verify path when no public key is set). |
| `clss.gateway.dev.identity_base_url` | Identity service base URL (upstream). Unset ⇒ resolved in-process over the deployable's own loopback. |
| `clss.gateway.dev.event_store_base_url` | Event-store base URL (upstream). Unset ⇒ resolved in-process over the deployable's own loopback. |
| `clss.gateway.dev.self_base_url` | The deployable's OWN base URL for in-process loopback forwarding. Maps to `CLSS_GATEWAY_DEV_SELF_BASE_URL`. UNSET defaults to `http://127.0.0.1:{PORT}` (PORT is what the deployable binds; Railway sets it, else 8080) so the in-process spine services AND the Wave-2 capability fronts (institution / scheduling / attendance / communication / teacher-growth / governance) resolve instead of returning 503 `upstream_unconfigured`. Set explicitly behind a proxy or for a split-out deploy. |
| `clss.gateway.dev.database_url` | Postgres connection for the immutable audit sink. |
| `clss.gateway.dev.track1_router_url` | Track 1 external LLM router endpoint (Ring 1). |
| `clss.gateway.dev.track2_endpoint_url` | Track 2 proprietary / edge endpoint (reserved slot, Ring 2). |

## event-store (`spine/event-store`)

| Name | Purpose |
|------|---------|
| `clss.eventstore.dev.database_url` | Postgres connection (append-only `platform.events`). Maps to `CLSS_EVENTSTORE_DEV_DATABASE_URL` (the Supabase pooler URL — the same DB the web `/api/governance` already writes to). SET (and asyncpg present) ⇒ `build_event_store` selects the Postgres adapter and appends are `persisted:true` for real; UNSET ⇒ the in-memory append-only log (clearly-labelled degrade, `persisted:false`). The in-process append seam (`backend/event_sink.py`) drives both on ONE shared background loop, which the real asyncpg pool requires. |
| `clss.eventstore.dev.supabase_url` | Supabase project URL for the event store. |
| `clss.eventstore.dev.supabase_service_key` | Supabase service-role key (service-role-mediated writes/reads). |
| `clss.eventstore.dev.jwt_public_key` | RS256 public key to verify identity tokens (same value as `clss.gateway.dev.jwt_public_key`). |
| `clss.eventstore.dev.identity_consent_check_url` | Identity consent-check endpoint for the gated read path. |

## governance & safety (`spine/governance`)

| Name | Purpose |
|------|---------|
| `clss.governance.dev.audit_database_url` | Postgres connection for the IMMUTABLE audit log (`platform.audit_log`, INSERT-only). Maps to `CLSS_GOVERNANCE_DEV_AUDIT_DATABASE_URL` (the Supabase pooler URL — the same DB the web `/api/governance` writes to). SET (and asyncpg present) ⇒ `build_audit_log` selects the Postgres adapter, its pool is opened on the shared sink loop, and toggle / break-glass / policy-version writes + the audit-trail READ are `persisted:true` for real; UNSET ⇒ the in-memory append-only ledger (observable degrade). |
| `clss.governance.dev.breakglass_database_url` | Break-glass record sink (immutable, reviewable). |
| `clss.governance.dev.consent_database_url` | Consent / retention / lineage store. |
| `clss.governance.dev.child_safety_classifier_url` / `_key` | Track-1 moderation/crisis classifier endpoint + key. |
| `clss.governance.dev.child_safety_edge_model_url` / `_key` | Track-2 (edge) classifier endpoint + key (kept separate from Track 1). |
| `clss.governance.dev.escalation_webhook_url` / `_key` | Qualified-human escalation channel endpoint + key. |

## database / migrations (`db`)

| Name | Purpose |
|------|---------|
| `clss.school.dev.database_url` | Postgres connection string used to apply the canonical migrations. |

## web surface (`surfaces/web`)

| Name | Purpose |
|------|---------|
| `NEXT_PUBLIC_CLSS_WEB_PROD_GATEWAY_URL` | Public gateway base URL the browser calls (RBAC+ABAC at the wall). |
| `CLSS_GATEWAY_URL` | Server-side gateway base URL the web's server client calls (the deployable's gateway). When set, the web's gateway-first reads/writes hit the real circuit (identity → gateway → capability → event); unset ⇒ the web degrades to its in-browser engine/mock behind the same interface. |
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
| `clss.aifabric.dev.gemini_api_key` | Gemini provider key. Backs **Vidya speech-to-speech** (REST pipeline: `gemini-2.5-flash` understands + replies, `gemini-2.5-flash-preview-tts` speaks — the realtime Live API is used instead when the tier exposes it) and the **live Track-1 text generator** (`app/generator.py` → `LiveTrack1Provider`): when present, a routed non-deterministic capability actually CALLS Gemini and the output passes the second-model cross-check + confidence gate; absent ⇒ refusal, never a fabricated answer. Read SERVER-SIDE ONLY; never sent to the browser. Track 1; routed through the gateway behind the permission ladder, the confidence gate, and child-safety on every free-text surface. See `docs/VOICE.md`. |
| `clss.aifabric.dev.track1_provider_key` | Generic Track 1 provider key. Its PRESENCE makes the router resolve an AVAILABLE Track-1 route, which is the gate that lets the orchestrator dispatch to the live generator above (absent ⇒ route unavailable ⇒ deterministic refusal). |
| `clss.aifabric.dev.crosscheck_model_key` | **Second-model cross-check** key (INVARIANT 7, generate-and-verify). An INDEPENDENT provider (OpenAI, a different family than the Gemini generator) confirms/refutes generated content; the confidence gate serves only when it agrees. Absent ⇒ the cross-check abstains and the gate stays CLOSED (nothing unverified is served). Read by NAME only; never returned or logged. |
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

## intelligence engine (`spine/intelligence`)

The engine derives mastery/gaps by REPLAYING events; it holds no credential of
its own. When configured it reads the REAL event log THROUGH the gateway
(`app/source.py` → `GatewayEventSource`); absent ⇒ it degrades to the in-memory
seed (observable, deterministic). A transport failure fails SAFE (no events),
never a fabricated history.

| Name | Purpose |
|------|---------|
| `clss.intelligence.dev.database_url` | The event source to replay. PRESENCE selects the live gateway-backed `EventSource`; absent ⇒ in-memory degraded source. |
| `clss.intelligence.dev.gateway_url` | The only egress; the event store is read THROUGH it (`POST /v1/route/event-store/readEvents`, purpose-asserted, INVARIANT 6). |
| `clss.intelligence.dev.gateway_token` | Bearer presented at the gateway wall for the event read. Read by NAME only; rides ONLY in the `Authorization` header, never logged. Absent ⇒ no read (fail safe, no fabricated events). |
| `clss.intelligence.dev.event_sink_url` | Where derived-state events (`mastery.updated` / `gap.detected` / `gap.resolved`) are POSTed THROUGH the gateway. Absent ⇒ in-memory append-only sink. |
| `clss.intelligence.dev.crosscheck_model_key` | Reserved for a future model-assisted gap cross-check; the deterministic gap rules run with no provider. Name only. |

## relationships & communication (`modules/communication`)

Holds no credential; every cross-context call passes the gateway. Translation
performs a REAL masked round-trip through the gateway to the model router
(`app/translation.py`), preserving subject terminology + code-switching; absent
or on any failure it degrades to a content-preserving passthrough.

| Name | Purpose |
|------|---------|
| `clss.communication.dev.gateway_url` | The only egress; translation + delivery + escalation all pass it. |
| `clss.communication.dev.translation_url` | The translation provider (model router / Gemini). PRESENCE (with the gateway) enables the live masked round-trip; absent ⇒ passthrough, tagged untranslated, subject terms still preserved. |
| `clss.communication.dev.gateway_token` | Bearer presented at the gateway wall for the live translation call. Read by NAME only; rides ONLY in the `Authorization` header, never in the request body or a log. Absent ⇒ degrade to passthrough. |

> The communication module exposes many more provider-URL names (chat/push/email/
> SMS/WhatsApp, safety, consent, workflow, transcription, companion-memory) — see
> `modules/communication/app/config.py`; each is names-only and degrades to a
> deterministic in-memory path when unset.

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
