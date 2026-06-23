# Learner record (B8)

The School-facing **composition of the evidence graph**: the evidence-linked
profile, the portfolio, and verifiable credentials. B8 **reads** governed,
consent + purpose-gated views of the learner graph and the evidence store — never
bulk reads, never PII — and composes them into a record the School can show. It
**never authors mastery** (that is a spine concern, A3); it never computes a
score; it never reads without a satisfied consent + purpose check.

## What it owns

| File | Responsibility |
| --- | --- |
| `app/access.py` | The consent + purpose gate on every read. **Denied-by-default.** Scope-, purpose-, audience-, and validity-checked. Raises `ConsentDenied` on a failed read. |
| `app/profile.py` | The evidence-linked profile — **independent vs support-dependent** mastery in **plain language, never a number**. Every item carries its **source** (evidence lineage) and its **permission controls** (who consented, who can see it, why). A boundary guard rejects any number/percentage/formula in learner-facing text. |
| `app/portfolio.py` | Curated artifacts with **provenance** (an artifact with no source events cannot be added). The shared view is gated. |
| `app/credentials.py` | **Verifiable, portable** credentials **under the learner's control**. No signing key configured → credential is `draft` and **not verifiable** (never faked). Export to anyone other than the holder is gated. |
| `app/events.py` | Portfolio / credential events (`portfolio.artifact_added`, `portfolio.artifact_featured`, `credential.issued`, `credential.revoked`). Attributed, append-only, PII-asserted, gateway-degrading. |
| `app/config.py` | Environment-only configuration, read by name. |

## Invariants honoured

- **PII-free** (1, 2): every event, profile item, artifact, and credential
  carries only the opaque `canonical_uuid` and opaque ontology / evidence ids.
- **Gateway** (3): every cross-service read/write passes the gateway. With none
  configured, reads come from in-memory governed-view fixtures and writes go to a
  clearly-labelled in-memory append-only sink.
- **Secrets env-only** (4): see the table below — names only, no values, ever.
- **Append-only** (5): a feature / revoke is a new event, never an in-place edit.
- **Consent is a primitive** (6): no read proceeds without a satisfied consent +
  purpose check. The Parent surface is gated like any other viewer — partnership,
  never surveillance.
- **Generate-and-verify spirit** (7): a credential is served as `verified` only
  when actually signed; absent a key it is `draft` and reported not-verifiable.
- **Evidence over assertion**: every profile item, gap note, artifact, and
  credential claim links to its source events or it cannot exist.

## Environment variables (names only — never commit a value)

Dotted convention `clss.<app>.<env>.<purpose>`; each maps to an env var with dots
and dashes uppercased to underscores (e.g. `CLSS_LEARNER_RECORD_DEV_GATEWAY_URL`).

| Dotted name | Purpose | Absent → |
| --- | --- | --- |
| `clss.learner-record.dev.gateway_url` | The only egress for governed reads / event writes. | degraded (in-memory) |
| `clss.learner-record.dev.gateway_token` | Bearer issued by identity (A1), presented at the gateway wall. | degraded |
| `clss.learner-record.dev.graph_read_url` | Governed read-view service for the learner graph + evidence store (A3). | in-memory governed-view fixtures |
| `clss.learner-record.dev.consent_authority_url` | Remote consent authority (A1/A7). | in-process gate (still denied-by-default) |
| `clss.learner-record.dev.event_sink_url` | Where portfolio/credential events are POSTed (through the gateway). | in-memory append-only sink |
| `clss.learner-record.dev.credential_signing_key` | Signing key for verifiable credentials. | credentials issued `draft`, not verifiable |

No `NEXT_PUBLIC_*` secret exists; nothing here is client-exposed.

## Tests

```
pytest
```

Import-safe and offline: the deterministic (degraded) paths are stdlib-only,
need no network, no DB, and no provider. The suite asserts: plain-language output
never leaks a number or formula; a read without a satisfied consent check is
denied; every profile item links to evidence; credentials are never faked as
verified without a key.
