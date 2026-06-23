# Architecture and boundary

How Classess School is shaped: three layers, one seam, three wires, a
secure-core boundary, and three rings. Ring 0 (this build) stands up the spine
and the contracts; the intelligence that consumes the seam matures in Ring 1+.

---

## 1. Three layers

- **Surfaces.** Thin. They compose views over capabilities and own no domain
  logic. The conversation-first home is the front door every role lands in; the
  role's pages are destinations it routes to and stays docked over. Built in
  Ring 0 as `surfaces/web` to prove the boundary.
- **Capability modules.** Classess School proper — feature-modular inside one
  deployable, each module owning its operational tables and emitting events.
  Contract-defined now; materialized slice by slice in Ring 1+ under `modules/`.
- **Spine.** Ecosystem-owned, built once, contracts immutable from line one.
  Role- and capability-agnostic. In Ring 0 this is `spine/identity`,
  `spine/gateway`, `spine/event-store`, the `contracts` package, and the `db`
  substrate.

---

## 2. The seam (events up, governed reads down)

Between every capability module and the spine there is one asymmetric seam:

- **Emit attributed events up** (the firehose) — every meaningful action becomes
  a clean, attributed, immutable event written to the event store.
- **Read governed, scoped views down** (the faucet) — no app bulk-reads the
  canonical store; reads pass a consent + purpose gate and return only the scoped
  projection.

This asymmetry buys independence, a clean security boundary, and durable value
at once. It is non-deferrable past the first commit, which is why the event
contract is frozen in Ring 0 even though the engines that consume it are Ring 1.

In this build the seam is realized by `spine/event-store`: the write path is
INSERT-only (`POST /v1/event-store/events`) and the read path
(`GET /v1/event-store/events`) mirrors `platform.read_events` in
`db/migrations/0006_governed_views.sql`, returning an empty set when no active
consent for the purpose exists.

---

## 3. Three connection wires

1. **Identity token** — who. One canonical, consented person. `spine/identity`
   mints a gateway-verifiable RS256 token whose claims carry the opaque
   `canonical_uuid`, the app, and the membership list — never PII.
2. **The gateway** — every call passes the wall. RBAC/ABAC scoped, schema-
   validated, audited. `spine/gateway` verifies the token, runs a deny-by-default
   policy engine, writes an immutable audit record for allow and deny, then
   routes.
3. **The event seam** — modules emit up and read governed views down (section 2).

Surfaces reach capabilities through gateway'd APIs. Modules reach intelligence
through events. The home reaches across by calling capabilities. That single
circuit is the whole platform.

---

## 4. The circuit

```
  identity ──► app ──► capability ──► event ──► intelligence
     ▲          (gateway wall on every hop)         │
     │                                              ▼
  outcome ◄── execute ◄── approve ◄── recommend ◄───┘
     │                  (permission ladder gates execute)
     └──────────────────► learn ──────────────────────►
            (fresh events feed the next reading)
```

Read it as one loop: a consented identity acts in an app, the app invokes a
governed capability, the action emits an attributed event, intelligence
interprets the accumulated events, it recommends, a human approves, the system
executes the approved action with least privilege, the outcome itself emits
events, and the loop learns. In Ring 0 the left arc (identity, app, capability,
event) is live; the right arc (intelligence, recommend, approve, execute) has
its contracts defined (`Verification`, `PermissionRung`, the recommendation
shape the web surface already renders) and is filled in Ring 1.

---

## 5. The secure-core boundary

- **Inside the wall (founder + Claude Code only):** identity, consent, gateway
  policy, the event/evidence contract and store, the evidence/mastery/gap engines
  (the IP, and the place a wrong judgment is existential), the AI fabric router
  and agents and verification substrate, governance/audit/secrets. In this build:
  `contracts/`, `spine/`, `db/`.
- **Outside the wall (developer lanes, against contracts, no credentials, no
  platform store, reviewed and scrubbed):** role surfaces, non-sensitive module
  logic, integration adapters. In this build: `surfaces/web`,
  `packages/design-system`, and (later) `modules/`. They consume the API; they
  never build the orchestrator or the agents, and they never read the canonical
  store directly.

The web surface enforces this for itself: it imports only contract TYPES and
design-system components, declares the gateway env var names in `lib/runtime.ts`,
and degrades to `lib/mock.ts` until the gateway is live — it never holds a
credential or touches the vault.

---

## 6. The three rings

- **Ring 0 — base (this build):** operational data substrate, identity and
  gateway, the immutable event store and the event/evidence contract, secrets and
  CI/CD.
- **Ring 1 — first-slice enablers:** the AI fabric router (thin, two-track slot,
  observability), the workflow and permission-ladder runtime, the content
  generate-and-verify substrate, the evidence/mastery/gap engines — each only as
  deep as the Student/Teacher slice forces.
- **Ring 2 — intelligence and scale:** full platform intelligence (profile,
  graph, feature store, prediction), connectors and the integration hub, comms
  lifecycle, analytics and experimentation depth, Track 2 models filled into the
  reserved router slot, multi-tenancy across group/franchise/programme/network.

The event contract is Ring 0 even though the intelligence that consumes it is
Ring 1-2: emit from line one, consume as it matures.
