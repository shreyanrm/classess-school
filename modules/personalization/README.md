# Personalization — implicit profiling engine

The **"get to know the user WITHOUT asking"** engine. It infers a learner's
**provisional** personalization profile — interests, preferred subjects, goal,
pace, strengths, preferred learning style — from **behavioural signals** and
**light onboarding choices**, **never from an explicit questionnaire**. Every
inferred trait carries its **evidence** and a **confidence**, and is always
**provisional** (re-derived on fresh signal), never a permanent label.

The **depth** of inference is bounded by the **consent + age tier** that legally
permits it (DPDP). A young-child tier infers far less than an adult tier; an
inference beyond the consented tier is **denied**. Profiles are **transparent**
(each trait is explainable: "inferred because…") and **revocable** (revoking
consent clears the inferred traits, leaving only what consent still permits).

PII-free throughout: keyed by the opaque `canonical_uuid` and opaque ontology
ids only.

## What it owns

| File | Responsibility |
| --- | --- |
| `app/consent_gate.py` | The consent + **AGE-TIER** gate. **Denied-by-default.** Each tier draws a strictly-nested ceiling on inferable traits (`child ⊂ teen ⊂ adult`) and caps confidence; a grant can narrow but never widen the tier door. An over-tier inference raises `InferenceDenied`. |
| `app/infer.py` | Infers traits from **behavioural signals + light onboarding choices** — there is no questionnaire input anywhere. Each trait links to its evidence signals, carries a confidence, an "inferred because…" explanation, and is provisional. Gated and confidence-capped per tier. |
| `app/profile.py` | The PII-free profile **projection by replaying signals**. **Idempotent** (same signals + consent → same profile) and **revocable** (replay through a revoked/narrowed consent clears the now-unpermitted traits). |
| `app/preferences.py` | Turns the profile into **surface hints** (suggested subjects/goal/pace) for onboarding + home. **No raw inference internals** (no confidence numbers, no evidence ids) ever reach the learner; hints are confidence-banded, calm plain language. |
| `app/events.py` | Emits `profile.updated` events. Attributed, append-only, PII-asserted, gateway-degrading. A revocation that clears traits is a **new** event, never an in-place edit. |
| `app/config.py` | Environment-only configuration, read by name. |

## Invariants honoured

- **PII-free** (1, 2): every signal, trait, profile, and event carries only the
  opaque `canonical_uuid` and opaque ontology / evidence ids. The event boundary
  asserts no PII-shaped key is present.
- **Gateway** (3): every cross-service read/write passes the gateway. With none
  configured, inference replays in-memory and events go to a clearly-labelled
  in-memory append-only sink.
- **Secrets env-only** (4): see the table below — names only, no values, ever.
  Nothing is `NEXT_PUBLIC_*`.
- **Append-only** (5): a profile update — including a revocation that clears
  traits — is a new event, never an in-place mutation.
- **Consent is a primitive** (6) + **DPDP age-tier**: no inference proceeds
  without a satisfied consent + scope check, and the depth is bounded by the age
  tier that legally permits it. Absence of a remote consent authority never opens
  a door (denied-by-default, never fail-open).
- **Permission ladder** (8): hints are suggestions a human acts on; nothing here
  auto-fires a consequential action.
- **Evidence over assertion** (principle 7): every trait links to its evidence
  signals or it cannot exist; no permanent judgement from a single interaction.

## Environment variables (names only — never commit a value)

Dotted convention `clss.<app>.<env>.<purpose>`; each maps to an env var with dots
and dashes uppercased to underscores (e.g.
`CLSS_PERSONALIZATION_DEV_GATEWAY_URL`).

| Dotted name | Purpose | Absent → |
| --- | --- | --- |
| `clss.personalization.dev.gateway_url` | The only egress for governed signal reads / event writes. | degraded (in-memory) |
| `clss.personalization.dev.gateway_token` | Bearer issued by identity, presented at the gateway wall. | degraded |
| `clss.personalization.dev.signal_read_url` | Governed read-view service for behavioural signals. | in-memory replay |
| `clss.personalization.dev.consent_authority_url` | Remote consent authority consulted on every inference. | in-process gate (still denied-by-default) |
| `clss.personalization.dev.event_sink_url` | Where `profile.updated` events are POSTed (through the gateway). | in-memory append-only sink |

No `NEXT_PUBLIC_*` secret exists; nothing here is client-exposed.

## Tests

```
pytest
```

Import-safe and offline: the deterministic (degraded) paths are stdlib-only,
need no network, no DB, and no provider. The suite asserts: inference works from
signals alone (no questionnaire); the consent/age-tier gate denies over-tier
inference and a minor tier infers strictly less; revocation clears inferred
traits; every trait carries evidence + confidence and is provisional; PII never
enters the profile; surface hints never leak inference internals.
