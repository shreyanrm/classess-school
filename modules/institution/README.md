# Classess School — Institution & policy module (B1)

The Ring 0 minimal-provisioning prerequisite, made real. An institution, its
structure, and its roster are the canonical schema every other module hangs off,
even while the UI is thin. Board-agnostic by construction.

This is a capability module over the secure core (behind the gateway). It never
owns a spine concern (identity, the event contract, the ontology, the
evidence/mastery engine). It holds the org hierarchy, the blueprint wizard,
policy inheritance, hyperlocalization, and logical multi-tenancy, and it emits
structure / roster / policy events on the contract envelope shape, keyed to the
opaque `canonical_uuid` only.

## What it owns

| File | Responsibility |
| --- | --- |
| `app/hierarchy.py` | The configurable org hierarchy and the scoped, time-bound relationship graph. Containment ladder `group -> region -> campus -> school -> department -> grade -> section` is configurable (use a subset, skip rungs, rename labels). A parent must out-rank its child. The relationship graph is many-to-many, each edge carrying a `valid_from`/`valid_to` window and a tenant scope, so the graph is correct as of a date and never spans tenants. |
| `app/blueprint.py` | The blueprint wizard. Takes a board-agnostic blueprint (structure, roster, policy), validates it as one gate (collecting all problems), and produces a tenant-scoped `InstitutionConfig` plus the append-only provisioning events. Building events is a PREPARE-class step: it returns the events and never sends them. |
| `app/policy.py` | Policy inheritance down the tree. A child inherits its parent's effective value and may override it; a locked policy set high is a floor descendants cannot override, and the highest lock wins. Every resolved value carries provenance (which node set it, inherited or not, locked or not) so the effective setting is explainable. Hyperlocalization (language, region, calendar) is policy with three well-known keys, resolved the same way. |
| `app/tenancy.py` | Logical multi-tenancy. Every record carries an opaque tenant scope; cross-tenant reads are denied by default. A widening grant is explicit and immutable; there is no wildcard and no silent global read. An unscoped record is never served. |
| `app/events.py` | Emits structure/roster/policy events on the contract envelope shape (`app . canonical_uuid . type . purpose . consent_ref`). Append-only; PII-free; every write passes the gateway. With no gateway configured, emission degrades to returning the event object. |
| `app/config.py` | Env-var names only. Reads configuration from the environment by name; no secret value is hardcoded, defaulted to a literal, or invented. |

## Invariants honoured

- **Opaque identity only (INVARIANT 1 + 2).** Every event and roster entry is
  keyed by the opaque `canonical_uuid` and opaque node / tenant ids. No builder
  accepts a name, email, or phone. A node `label` is a place's own display name,
  never a person.
- **Append-only events (INVARIANT 5).** The emitter only appends; there is no
  update or delete path. The envelope has no mutation route.
- **Every cross-service call passes the gateway (INVARIANT 3).** Event egress is
  never direct; with no gateway configured, emission degrades to returning the
  event object. The wired path raises rather than ever attempt unauthenticated
  egress.
- **Tenant isolation (INVARIANT 10).** Every record carries a tenant scope;
  cross-tenant reads are denied by default and widened only by an explicit,
  auditable grant.
- **Secrets are env-only (INVARIANT 4).** Config is read from the environment by
  name. No secret value is hardcoded, defaulted to a literal, or invented. No
  server secret is exposed to a browser or a `NEXT_PUBLIC_` var.
- **Agents hold no credentials (INVARIANT 8).** No auth token is constructed
  from a literal anywhere; a real sink reads its token from the environment by
  name. Provisioning and policy locks are governed; nothing consequential
  auto-fires.
- **Explainable intelligence.** Every resolved policy states why it applies
  (source node, inherited-or-set, locked-or-not). Hyperlocalization invents no
  default — an unset locale stays unset for the institution to choose.

## Environment variables (names only)

Dotted names follow `clss.<app>.<env>.<purpose>` and map to env vars
(uppercased, dots to underscores). No value appears in code; absence degrades
gracefully.

| Dotted name | Env var | Purpose |
| --- | --- | --- |
| `clss.institution.dev.gateway_url` | `CLSS_INSTITUTION_DEV_GATEWAY_URL` | The single egress. Every cross-service call passes the gateway. Unset -> degraded. |
| `clss.institution.dev.event_sink_url` | `CLSS_INSTITUTION_DEV_EVENT_SINK_URL` | Where structure/roster/policy events are POSTed through the gateway. Unset -> events are returned, never sent. |
| `clss.institution.dev.database_url` | `CLSS_INSTITUTION_DEV_DATABASE_URL` | Canonical store for institution config. Unset -> in-memory only. |
| `clss.institution.dev.identity_url` | `CLSS_INSTITUTION_DEV_IDENTITY_URL` | Identity service base (membership + consent resolution). Unset -> caller-supplied opaque ids are trusted; no PII resolved. |
| `clss.institution.dev.ontology_url` | `CLSS_INSTITUTION_DEV_ONTOLOGY_URL` | Ontology service base (board -> grade -> subject mapping). Unset -> opaque ontology ids accepted without remote validation. |

`CLSS_INSTITUTION_DEV_ENV` selects the environment label (default `dev`).

## Tests

```
python -m pytest
```

Tests cover hierarchy build + traversal, the time-bound relationship graph,
policy inheritance + override + locking, hyperlocalization resolution, tenant
isolation (cross-tenant reads denied by default), blueprint validation +
provisioning, and graceful event-emission degradation. Import-safe: no network,
no DB, no secret value required.
