# Classess School — Relationships & communication (B9)

The relationships layer: the companion / care surface, parent engagement and
parent–teacher partnership, the communication hub, and safeguarding — the
child-safety subsystem that runs on every free-text surface. A capability module
over the secure core (the companion and the safety subsystem are the highest-
rigor parts).

Four non-negotiables run through every surface here:

- **The companion is bounded.** It is role-shaped and supportive, but it can
  never foster manipulation, exclusivity, or dependence. Every reply — scripted
  or model-generated — passes a boundary wall that rejects dependence/secrecy/
  engagement-baiting wholesale. It points the learner back toward people and
  independent effort.
- **Serious matters escalate to qualified humans.** Child-safety screens every
  free-text message first. A flagged or crisis message is never answered by a
  bot — it is handed to a qualified human (a counsellor / safeguarding lead),
  calmly and honestly. The companion never tries to counsel a crisis.
- **No unmonitored channels.** There is no constructor for an un-screened
  free-text channel. `safeguarding.open_channel` refuses to open a channel that
  is not bound to the classifier — structurally.
- **The parent surface is partnership and pride, never surveillance.** Every
  cross-context read is consent-gated (fail-closed), and surveillance-shaped
  purposes are refused even with a consent grant. Consent permits partnership,
  never monitoring.

## What it owns

| File | Responsibility |
| --- | --- |
| `app/companion.py` | The role-shaped, **bounded** companion. `check_boundaries` rejects any reply expressing dependence / exclusivity / manipulation; `respond` screens every message and **escalates** serious matters to a qualified human instead of counselling them; `vet_generated_reply` is the second wall over an orchestrator candidate. Degrades to a vetted, scripted, anti-dependence path with no orchestrator. |
| `app/safeguarding.py` | The **child-safety subsystem**: moderation + crisis detection (`classify`), escalation to a qualified human (`escalate` / `screen`), and **no unmonitored channels** (`open_channel` refuses a guard-less channel; `MonitoredChannel.admit` is the only ingress). Fail-safe: with no A7 service it runs a deterministic on-device classifier that flags **up** under ambiguity and never silences a crisis. |
| `app/hub.py` | The **communication hub**. `post` always screens (no unmonitored channel); a message can become a **routed, owned, tracked task** (`route_to_task`) with an owner, due date, why, and an explicit human-advanced lifecycle. Cross-context routing is **consent-gated**. Tasks are advanced only by a human (permission ladder). |
| `app/parent_partnership.py` | Parent engagement framed as **partnership + pride**, in plain language (no raw number / formula). `read_child_context` gates every **cross-context read** on a satisfied consent grant (fail-closed) and **refuses surveillance** purposes outright. |
| `app/translation.py` | The **multilingual + code-switching** interface. Preserves protected subject terminology verbatim (`mask`/`restore` round-trip), detects and preserves code-switch spans, and degrades to a **content-preserving pass-through** that never drops or garbles text and never sends text off-box without the gateway. |
| `app/events.py` | Emits `message.sent`, `meeting.scheduled`, `sentiment.observed`, and `safeguarding.escalated` on the attributed, append-only envelope. Opaque ids only — **never the message body**; `message.sent` refuses an unscreened message; a safeguarding escalation rides the `intervention` purpose. |
| `app/config.py` | Env-var **NAMES only**. Degrades gracefully when nothing is set. |

## Invariants honoured

- **Opaque identity only (INVARIANT 1 + 2).** Every event, escalation, task, and
  partnership card is keyed by `canonical_uuid` and opaque context/meeting/
  surface ids. No builder accepts a name/email; the message body never rides an
  event — only its safety classification does.
- **Append-only events (INVARIANT 5).** The emitter only appends; it never
  updates or deletes.
- **Consent gates every cross-context read (INVARIANT 6).** A parent reading a
  child's context and a hub message routed into a different context both require
  a satisfied consent ref; with none, the action is denied and nothing is
  leaked.
- **Permission ladder (INVARIANT 8).** Advancing/closing a tracked task and
  acting on an escalation are human-owned; the system prepares and routes but
  never auto-fires. A crisis is never bot-handled.
- **Child-safety on every free-text surface.** The companion and the hub both
  route all free text through `safeguarding` before showing, storing, or
  replying. There is no path to an unmonitored channel.
- **Every cross-service call passes the gateway.** Event egress, the
  orchestrator, the safety service, the consent authority, and the translation
  provider are reached only through the gateway; with none configured the module
  degrades to clearly-labelled in-memory / on-device paths.
- **Secrets are env-only (INVARIANT 4).** No secret value is read at import or
  stored as a literal; only the dotted NAMES below are referenced. No
  `NEXT_PUBLIC_` secret.

## Configuration (environment variable NAMES only)

Dotted convention `clss.<app>.<env>.<purpose>`; the OS key is the dotted name
uppercased with dots/dashes → underscores (e.g.
`clss.communication.dev.gateway_url` → `CLSS_COMMUNICATION_DEV_GATEWAY_URL`). All
are optional; absence keeps the module in deterministic, in-memory / on-device
mode.

| Dotted name | OS env var | Purpose |
| --- | --- | --- |
| `clss.communication.dev.gateway_url` | `CLSS_COMMUNICATION_DEV_GATEWAY_URL` | The only egress. Every cross-service call passes the gateway. |
| `clss.communication.dev.event_sink_url` | `CLSS_COMMUNICATION_DEV_EVENT_SINK_URL` | Where emitted events are POSTed (through the gateway). |
| `clss.communication.dev.database_url` | `CLSS_COMMUNICATION_DEV_DATABASE_URL` | The operational store (messages, tasks, meetings). |
| `clss.communication.dev.orchestrator_url` | `CLSS_COMMUNICATION_DEV_ORCHESTRATOR_URL` | The A4 / Vidya orchestrator the companion speaks through (structured-output + confidence gate). |
| `clss.communication.dev.safety_url` | `CLSS_COMMUNICATION_DEV_SAFETY_URL` | The A7 child-safety service. Unset → the on-device classifier floor (fail-safe). |
| `clss.communication.dev.consent_url` | `CLSS_COMMUNICATION_DEV_CONSENT_URL` | The A1 consent authority for cross-context reads. |
| `clss.communication.dev.workflow_url` | `CLSS_COMMUNICATION_DEV_WORKFLOW_URL` | The A5 workflow engine that carries an escalation / task to a qualified human. |
| `clss.communication.dev.translation_url` | `CLSS_COMMUNICATION_DEV_TRANSLATION_URL` | The translation provider (multilingual + code-switching). |

No secret VALUE is ever hardcoded. The gateway bearer token is read from the
environment by name at the point of egress (not implemented while no provider
exists); it is never exposed to the browser and never a `NEXT_PUBLIC_` var.

## Tests

```
pytest          # from this directory
```

Import-safe and offline: the whole suite runs with no network, no DB, and no
provider, exercising the deterministic (degraded) paths — the supported paths
until the gateway, orchestrator, safety service, consent authority, and
translation provider are wired. Coverage includes: the companion refuses
dependence-forming behavior and escalates crisis signals; safeguarding flags +
escalates risky content and allows no unmonitored channel; a cross-context read
without consent is denied.
