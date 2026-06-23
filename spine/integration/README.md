# Integration (FLUID) — the two-way standards bridge (spine A6)

The connector framework and standards adapters that let the platform run as the
intelligence layer on top of an existing system, take it over, or just exchange
data. It speaks the standards school systems already speak, and maps everything
into the spine's opaque, board-agnostic ontology and canonical identity.

```
integration/
  app/
    config.py        # env-only config (NAMES only); Track 1 / Track 2 separated
    models.py        # standards-neutral, PII-free internal shapes + PII backstop
    mapping.py       # the identity + ontology seam (opaque source_key, no PII)
    health.py        # connector-health monitoring (states + hysteresis)
    connector.py     # the connector framework base
    events.py        # relays activity into the immutable event store via gateway
    registry.py      # builds + tracks the connector set with health
    adapters/        # LTI 1.3, OneRoster 1.2, xAPI, Caliper, QTI, SCORM,
                     # Clever, ClassLink, Ed-Fi, CASE, MCP
  tests/             # pytest: roster->opaque, xAPI/Caliper round-trip,
                     # health states, QTI/OneRoster/SCORM/LTI/CASE parse
```

## What it bridges

| Standard | Direction | What the adapter does |
| --- | --- | --- |
| LTI 1.3 | in / out | Validate launch claim shape, map to an opaque ref; build AGS score + deep-linking descriptors (consequential, approval-gated) |
| OneRoster 1.2 | in / out | Import CSV + REST rosters and learning objectives into PII-free shapes; results passback (consequential) |
| xAPI | in / out | Round-trip statements through the internal activity shape with an opaque actor |
| Caliper | in / out | Round-trip events through the internal activity shape with an opaque actor |
| QTI 2.x / 3.0 | in / out | Parse assessment items (choice, text-entry, extended-text, match); serialise back |
| SCORM 1.2 / 2004 / cmi5 | in | Parse `imsmanifest.xml` into a manifest shape; relay runtime via the xAPI seam |
| Clever / ClassLink | in | Sync rosters into PII-free shapes and enrollments |
| Ed-Fi | in | Map Ed-Fi resources + section associations into PII-free shapes |
| CASE | in | Parse a framework into ontology outcome candidates with a child/parent hierarchy |
| MCP | surface | Expose the bridge as governed MCP tools; consequential tools are prepared, not executed |

## How the invariants are realised here

- **PII vaulted + segregated (1, 2).** External records carry PII (name, email,
  SIS id). Only the opaque, salted `source_key` — and, when identity is online,
  the random `canonical_uuid` — ever crosses a boundary. `assert_no_pii` is a
  hard backstop on every cross-boundary object and detects PII field names
  regardless of separator style (`givenName` == `given_name`).
- **The canonical UUID is opaque (2).** `source_key` is `HMAC-SHA256(salt,
  standard:normalized_id)` — one-way, salt-scoped, stable for re-import,
  unlinkable to a person without the identity vault.
- **Every call passes the gateway (3).** Adapters hold **no** credentials. Any
  outbound effect (grade passback, LRS/Caliper forward, deep-linking) is
  described as a descriptor handed to a governed gateway capability.
- **Secrets are environment-only (4).** Every value is read by env var NAME; no
  value is hardcoded or logged. Degraded-mode startup reports the missing
  config by NAME only.
- **Events immutable + append-only (5).** `events.py` builds attributed,
  PII-free event inputs and posts them through the gateway; nothing is mutated.
- **Consent gates the relay (6).** An activity event refuses to build without a
  `consent_ref`.
- **Permission ladder (8).** Consequential connector actions are prepared and
  approval-gated, never auto-fired. The MCP surface returns a prepared,
  approval-required descriptor for consequential tools.
- **Two tracks stay separate (11).** Track 1 (external standards endpoints) and
  the reserved Track 2 slot are distinct fields in `config.py`.
- **Child-safety on free text (A7).** The MCP surface screens every declared
  free-text field through an injected guard; with no guard wired it refuses
  rather than pass unscreened input.

## Degraded mode

With nothing configured the package starts in a clearly-labelled DEGRADED mode:
every adapter still parses, maps and round-trips against in-process data; the
content connectors (QTI, SCORM) are fully functional; endpoint-backed connectors
report `UNCONFIGURED` so an operator sees exactly which standards are live. No
network and no DB are required for the suite to pass.

## Env var inventory (names only; values via Infisical)

Each dotted name is read from the shell-safe `CLSS_INTEGRATION_DEV_*` form
(`clss.integration.dev.gateway_base_url` ->
`CLSS_INTEGRATION_DEV_GATEWAY_BASE_URL`).

Core (presence moves the layer off the degraded path):
- `clss.integration.dev.gateway_base_url`
- `clss.integration.dev.event_store_url`
- `clss.integration.dev.identity_base_url`
- `clss.integration.dev.ontology_base_url`
- `clss.integration.dev.jwt_public_key` (token verify; public key only)
- `clss.integration.dev.source_key_salt` (salt for the opaque source_key)

Track 1 — external standards endpoints (route NAMES, not secrets):
- `clss.integration.dev.lti_platform_issuer`
- `clss.integration.dev.lti_jwks_url`
- `clss.integration.dev.oneroster_base_url`
- `clss.integration.dev.clever_base_url`
- `clss.integration.dev.classlink_base_url`
- `clss.integration.dev.edfi_base_url`
- `clss.integration.dev.case_registry_url`
- `clss.integration.dev.caliper_endpoint_url`
- `clss.integration.dev.xapi_lrs_url`

Track 2 — proprietary / edge (reserved slot, filled later, no re-architecture):
- `clss.integration.dev.track2_connector_url`

Staging and prod use `clss.integration.staging.*` / `clss.integration.prod.*`;
the `ENV_PREFIX` in `config.py` is the single place to switch the resolved
environment.

## Tests

```
cd spine/integration && python -m pytest
```

The suite is import-safe and passes with no network, no DB and no live keys:
roster imports map to opaque ids with no PII bleed; xAPI/Caliper statements
round-trip; connector-health states (including hysteresis and `UNCONFIGURED`);
QTI/OneRoster/SCORM/LTI/CASE parse; the event seam refuses without consent; the
MCP surface gates consequential tools and free text.
