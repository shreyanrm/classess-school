# Governance & safety (spine A7)

The most powerful surfaces are the best governed. This package is the spine's
governance core: immutable audit, break-glass, the AI control centre,
consent / retention / lineage, the child-safety subsystem, and tenant isolation.

It is **deterministic-first and dependency-free**: every module runs on the
standard library alone, is import-safe, and the test suite passes with **no
network and no database**. Durable backends (a Postgres audit sink, a live
moderation/crisis classifier) wire in later behind named env vars with no
re-architecture. With no live keys/DB the package degrades to clearly-labelled
in-memory / abstaining behavior — it never fabricates a result or a key.

## Modules

| Module               | What it owns                                                                                                  | Invariant |
| -------------------- | ------------------------------------------------------------------------------------------------------------- | --------- |
| `audit.py`           | Immutable audit layer. `record` (append) + `query` (read) only — no update/delete surface exists.             | 9         |
| `breakglass.py`      | Break-glass: privileged access demands a non-empty reason, is recorded immutably, time-boxed, and reviewable. | 9, 8      |
| `control_centre.py`  | AI control centre: model usage, Track 1 / Track 2 separated view, confidence-gate stats, emergency disable.   | 7, 11     |
| `consent.py`         | Consent + retention + lineage services. The cross-context read gate; lineage on every insight.                | 6         |
| `child_safety.py`    | Moderation, crisis detection, escalation to qualified humans, no unmonitored channels — every free-text surface. | 12     |
| `tenancy.py`         | Tenant isolation policy across group / franchise / programme / network. Default deny; explicit read-down only. | 10        |
| `config.py`          | Env-only settings under `CLSS_GOVERNANCE_DEV_`. Values default to `None`; never hardcoded.                     | 4         |
| `models.py`          | Shared records. Ledger entries are `frozen` dataclasses. No PII — opaque `canonical_uuid` refs only.           | 1, 2      |

## How the invariants are enforced here

- **Audit is immutable (9).** `AuditLog` exposes only `record` and `query`. The
  in-memory ledger is append-only and returns copies; the Postgres adapter
  writes `platform.audit_log` with INSERT-only grants and an immutability
  trigger as the hard wall. There is no mutation method to call.
- **Break-glass (9, 8).** `BreakGlassService.open` raises `ReasonRequiredError`
  without a non-empty reason, writes a **privileged** immutable audit entry, and
  time-boxes the grant. Four-eyes capabilities require an `approved_by` second
  principal. `list_for_review` / `review` make every grant reviewable; review
  and close **append superseding records**, never edit the original.
- **Control centre (7, 11).** `track_view()` reports Track 1 and Track 2 in
  **separate buckets**, never summed; an unknown track is rejected.
  `confidence_gate_stats()` exposes served vs withheld and mean served
  confidence. `emergency_disable()` halts a capability immediately and
  `guard()` makes a disabled capability genuinely un-runnable; every
  disable/enable is a privileged audit entry.
- **Consent (6).** `ConsentService.is_satisfied(subject, purpose)` is the gate —
  closed by default, opened only by an active (non-revoked) grant for that exact
  purpose, and re-closed the instant consent is revoked. `RetentionService`
  reports KEEP / EXPIRE / LEGAL-HOLD; expiry severs the linkable row (the
  storage layer performs the purge). `LineageService.build_lineage` refuses an
  insight that lacks a consent ref or any source — **lineage on every insight**.
- **Child-safety (12).** `ChildSafetySubsystem.assess` raises
  `UnmonitoredChannelError` for any surface not registered as monitored — there
  is no unmonitored free-text path. It flags/blocks on moderation categories and
  marks CRISIS on self-harm/abuse/danger signals (crisis always overrides a
  softer verdict), raising an `Escalation` to a qualified human and recording it
  immutably. The default classifier is a deterministic lexicon screen that
  **abstains** (low confidence) on non-matches rather than asserting "safe", so
  ambiguous text fails toward review (7). Live Track 1 / Track 2 classifiers wire
  in via the `SafetyClassifier` seam behind their **separate** env keys (11).
- **Tenant isolation (10).** `TenancyPolicy` is a pure, deterministic yes/no the
  gateway wall consults (enforced at the wall, not in services — 3). Default
  deny; a parent may read into explicitly-registered descendants; a child never
  reads up into a parent or sideways into a sibling.
- **No PII (1, 2).** Every record references identity only by the opaque
  `canonical_uuid` (subjects) or opaque actor refs. No names, no PII, anywhere.

## Env vars (names only — INVARIANT 4)

Secrets are environment-only, read by NAME, never hardcoded. Names follow
`clss.<app>.<env>.<purpose>` and map to OS env keys by uppercasing and replacing
`.`/`-` with `_`. The shared prefix for this app/env is `CLSS_GOVERNANCE_DEV_`.
Every field defaults to `None`; absence degrades to a clearly-marked in-memory /
abstaining result, never a fabricated value and never an invented key.

| Secret name (dotted)                          | OS env var                                    | Purpose                                            |
| --------------------------------------------- | --------------------------------------------- | -------------------------------------------------- |
| `clss.governance.dev.audit_database_url`      | `CLSS_GOVERNANCE_DEV_AUDIT_DATABASE_URL`      | Immutable audit sink (INSERT-only)                 |
| `clss.governance.dev.breakglass_database_url` | `CLSS_GOVERNANCE_DEV_BREAKGLASS_DATABASE_URL` | Break-glass record sink (immutable, reviewable)    |
| `clss.governance.dev.consent_database_url`    | `CLSS_GOVERNANCE_DEV_CONSENT_DATABASE_URL`    | Consent / retention / lineage store                |
| `clss.governance.dev.child_safety_classifier_url` | `CLSS_GOVERNANCE_DEV_CHILD_SAFETY_CLASSIFIER_URL` | Moderation/crisis classifier endpoint (Track 1) |
| `clss.governance.dev.child_safety_classifier_key` | `CLSS_GOVERNANCE_DEV_CHILD_SAFETY_CLASSIFIER_KEY` | Moderation/crisis classifier key (Track 1)      |
| `clss.governance.dev.child_safety_edge_model_url` | `CLSS_GOVERNANCE_DEV_CHILD_SAFETY_EDGE_MODEL_URL` | On-edge classifier endpoint (Track 2 — separate)|
| `clss.governance.dev.child_safety_edge_model_key` | `CLSS_GOVERNANCE_DEV_CHILD_SAFETY_EDGE_MODEL_KEY` | On-edge classifier key (Track 2 — separate)     |
| `clss.governance.dev.escalation_webhook_url`  | `CLSS_GOVERNANCE_DEV_ESCALATION_WEBHOOK_URL`  | Qualified-human escalation channel endpoint        |
| `clss.governance.dev.escalation_webhook_key`  | `CLSS_GOVERNANCE_DEV_ESCALATION_WEBHOOK_KEY`  | Qualified-human escalation channel key             |

Track 1 (external classifier) and Track 2 (on-edge model) have **distinct,
separately-named** key fields and are never read into one shared slot
(INVARIANT 11).

## Tests

`tests/` covers: audit append + immutable query; break-glass reason requirement,
immutable privileged recording, review/close, four-eyes, and TTL expiry; control
centre track separation, gate stats, and emergency disable halting a capability;
the consent gate (grant/revoke), retention KEEP/EXPIRE/LEGAL-HOLD, and lineage
required-on-every-insight; child-safety crisis escalation, moderation flagging,
crisis-overrides-moderation, and the no-unmonitored-channel refusal; tenant
isolation read-down / no-read-up / sibling denial; and env-only config with
Track 1/2 separation. Import-safe, no network, no DB.

```
python -m pytest spine/governance
```
