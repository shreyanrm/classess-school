# AI fabric (spine A4)

The model router and the generate-and-verify substrate. Exposes generation,
evaluation, and conversation behind structured-output validation and a
**confidence gate**. Nothing generated is served unverified.

This package is deterministic-first: the router, the verifier, the confidence
gate, the orchestrator, and observability run on the standard library alone. No
live LLM key and no tracing backend are required for the deterministic paths or
the tests. Live providers and tracing are wired later behind named env vars,
with no re-architecture.

## The two tracks (INVARIANT 11 — never conflated)

Track 1 and Track 2 are **distinct config structures** in `router.py`, with
distinct ownership and distinct env var names. Selection respects which track
owns a capability and never crosses tracks.

- **Track 1 — external LLM routing** (`Track1Config`, present now). Routes
  through an external gateway (e.g. LiteLLM). The provider key is read by env
  var NAME; when absent the router returns a clearly-marked *unavailable*
  result and never fabricates content.
- **Track 2 — proprietary / edge models** (`Track2Config` + `track2.py`). The
  reserved slot, now **filled** with an edge SLM adapter. Distinct ownership
  (proprietary / edge models team, Ring 2) and distinct env var names. Enabling
  it stayed a config change — enable, bind per-tier model labels, supply its
  endpoint key by name — not a re-architecture.

## Track 2 — proprietary / edge SLM adapter (`track2.py`)

Track 2 serves the high-frequency **edge "ocean"**: small, fast, on-device-style
SLMs for low-stakes, latency-sensitive work. It is the proprietary / edge
counterpart to Track 1 and is owned by a **different team**. It runs **only on
Track 2** and is **never conflated** with Track 1 (INVARIANT 11): its
capabilities register with `track=2`, and its endpoint URL and key come from
Track 2's **own** named secrets, distinct from Track 1's.

Two governed edge capabilities ship, each `track=2`, `requires_verification`
true, and on the `RECOMMEND` rung with a least-privilege scope (a single purpose
code + minimal data scopes — the opaque conversation handle / ontology refs, no
PII):

- **`content.generate-hint`** — a short hint on a fast edge SLM
  (`edge-slm-hint`), purpose `hint_generation`.
- **`classify.intent`** — free-text intent classification on a fast edge SLM
  (`edge-slm-intent`), purpose `intent_classification`.

Both map to the **edge** tier in the router's auditable table, so the router
selects the edge tier for them. Selection respects the owning track: a `track=2`
intent resolves on Track 2 and **never borrows Track 1's key** — if Track 1 has a
key but Track 2 does not, a Track 2 intent stays unavailable.

The `Track2Adapter`:

- holds **no credentials** of its own — it reads Track 2's named endpoint key by
  NAME only when it must call the endpoint, and never returns or logs it;
- **degrades gracefully**: with no endpoint URL, no key, or no wired SLM seam,
  every entrypoint returns `provider_available=false`, `refused=true`, and no
  text — a clearly-marked unavailable result naming the env vars to set, **never
  fabricated** content;
- runs output behind the **same confidence gate** (INVARIANT 7): deterministic
  checks (non-empty output, confidence in `[0,1]`), then an independent
  second-model agreement, then the threshold. With no live endpoint the second
  model abstains and the gate stays closed — text is withheld, never fabricated.

Helpers: `register_track2_capabilities(registry)` registers the edge
capabilities on an existing registry alongside the (Track 1) default set;
`track2_config()` returns the router `Track2Config` with the edge model bound.

### Tiers

The router maps a task class to a tier:

- **frontier** — the hardest, rarest reasoning (used sparingly),
- **mid** — high-volume capable work (the workhorse),
- **edge** — the high-frequency ocean of small, fast, low-stakes tasks.

Mapping is an explicit, auditable table; unknown task classes fall through to a
difficulty/latency heuristic.

## Generate-and-verify and the confidence gate (INVARIANT 7)

`verify.py` runs, in order:

1. **Deterministic checks first** — symbolic/numeric where possible. For a
   math/physics item: re-evaluate the expression (a safe `ast`-based evaluator,
   no `eval`, no names, no calls), numeric bound checks, and unit consistency.
   This needs no LLM and is the verified ground truth.
2. **Second-model cross-check** — an independent model agrees or disagrees,
   behind the `SecondModelChecker` interface. With no live provider the default
   `AbstainingSecondModel` does NOT agree (and reports zero confidence), which
   keeps the gate closed — it degrades safely rather than serving blind.
3. **The confidence gate** — content is **served** only when deterministic
   checks pass AND the second model agrees AND confidence >= threshold (default
   0.85). Otherwise it is **withheld** and flagged for human review with a
   reason.

## The capability registry (INVARIANT 8 — permission ladder)

`capability_registry.py` holds governed, least-privilege capabilities (e.g.
`content.generate-practice-item`, `evaluate.response`, `explain.step`,
`conversation.companion-turn`). Each declares input/output schema refs (contract
ids), the track it runs on, a least-privilege scope (one purpose code + minimal
data scopes), whether it requires verification, and its consequence rung. Agents
invoke capabilities here and hold no credentials.

## The orchestrator

`orchestrator.py` is a thin Vidya entrypoint. It resolves a capability, enforces
least privilege (purpose must match) and the permission ladder (a consequential
capability such as grading returns `requires_approval` rather than executing
until an explicit human `approval_token` is present), routes on the owning
track, runs generate-and-verify, and returns a structured result with the
verification block. When no provider is available and no deterministic handle
exists, it returns a well-formed refusal — never fabricated content.

## Voice — Vidya speech-to-speech (Gemini Live native audio)

`voice.py` adds a Track 1 speech-to-speech capability
(`conversation.voice-speech-to-speech`): learner audio in, spoken reply out. It
is registered in the capability registry with `track=1`, `requires_verification`
true, and a least-privilege scope (purpose `voice_companion_dialogue`, the single
data scope `conversation.context` — the opaque conversation handle only, no PII).

It exposes two entrypoints on `VoiceAdapter`:

- **`mint_browser_session()`** — the browser handshake. It mints an
  **ephemeral, short-lived session token** so a browser can open a Gemini Live
  session **without ever seeing the raw provider key**. The raw key is read by
  NAME on the server, handed to the provider's token-mint seam, and only the
  short-lived token comes back. The raw key is never returned and never logged.
  If the provider SDK is absent or the key is unset, it returns
  `provider_available=false` with no token — never a fabricated one. A token
  that comes back equal to the raw key is rejected (defence in depth).
- **`respond_speech_to_speech()`** — a server-side turn, audio in to audio out,
  run behind the **confidence gate** (INVARIANT 7): deterministic checks (the
  reply has audio and a transcript to cross-check), then an independent
  second-model agreement, then the threshold. With no live provider the second
  model abstains and the gate stays closed — audio is withheld, never
  fabricated. The capability sits on the `RECOMMEND` rung; consequential
  follow-ons still require an explicit human `approval_token` (INVARIANT 8).

### The ephemeral-token model

The raw `gemini_api_key` stays server-side at all times. The browser receives
only a short-fuse token (default TTL 120s) minted via the provider; if it leaks
it expires quickly and cannot be used to mint more. No `NEXT_PUBLIC_` exposure,
no server secret in the browser (INVARIANT 4).

## Observability

`observability.py` is a span interface for cost / latency / quality. It no-ops
without a backend (`NullTraceSink`); a `BufferingTraceSink` is provided for
tests. The tracing endpoint is read by env var name.

## Env vars (names only — INVARIANT 4)

Secrets are environment-only, read by NAME, never hardcoded. Names follow
`clss.<app>.<env>.<purpose>` and are mapped to OS env keys by uppercasing and
replacing `.`/`-` with `_`.

| Secret name (dotted)                          | OS env var                              | Purpose                                  |
| --------------------------------------------- | --------------------------------------- | ---------------------------------------- |
| `clss.aifabric.dev.track1_router_url`         | `CLSS_AIFABRIC_DEV_TRACK1_ROUTER_URL`   | Track 1 external router base URL         |
| `clss.aifabric.dev.track1_provider_key`       | `CLSS_AIFABRIC_DEV_TRACK1_PROVIDER_KEY` | Track 1 provider key (held by the router)|
| `clss.aifabric.dev.track2_endpoint_url`       | `CLSS_AIFABRIC_DEV_TRACK2_ENDPOINT_URL` | Track 2 proprietary/edge endpoint URL    |
| `clss.aifabric.dev.track2_endpoint_key`       | `CLSS_AIFABRIC_DEV_TRACK2_ENDPOINT_KEY` | Track 2 endpoint key                     |
| `clss.aifabric.dev.tracing_url`               | `CLSS_AIFABRIC_DEV_TRACING_URL`         | Observability/tracing backend URL        |
| `clss.aifabric.dev.tracing_key`               | `CLSS_AIFABRIC_DEV_TRACING_KEY`         | Observability/tracing backend key        |
| `clss.aifabric.dev.gemini_api_key`            | `CLSS_AIFABRIC_DEV_GEMINI_API_KEY`      | Gemini Live voice key — server-side only; mints ephemeral browser tokens, never sent to a client |

No key value appears in this repository. Absence degrades to a clearly-marked
unavailable/refusal, never a fabricated answer and never an invented key.

## Tests

`tests/` covers the deterministic verifier, the confidence gate (served vs
withheld), router tier selection, track separation, the permission ladder, and
the no-provider refusal path. `tests/test_track2.py` adds the Track 2 edge SLM
adapter: Track 1 and Track 2 are selected for the right task classes and never
conflated, Track 2 degrades with no endpoint, and the confidence gate still
applies to Track 2 output. Import-safe, no network.

```
python -m pytest spine/ai-fabric
```
