# Architecture and boundary

## Three layers

- **Surfaces** — Admin, Teacher, Student, Parent. Thin; they compose views over modules and own no domain logic. **Vidya is the home itself** — the conversation-first front door every role lands in. The role's pages are destinations Vidya routes to and stays docked over, not a separate spine it merely sits beside.
- **Capability modules** — Classess School, feature-modular inside one deployable with clean internal boundaries (splittable into separate services later). Each owns its operational data and emits events.
- **Spine** — ecosystem (KGtoPG), built once, contracts immutable from line one. Role- and capability-agnostic.

## The seam

Between every capability module and the spine: emit attributed events up (firehose), read governed scoped views down (faucet). No app bulk-reads the canonical store. This asymmetry gives independence, a clean security boundary, and durable value at once. Non-deferrable past the first commit.

## Connection model — three wires

1. **Identity token** — who (one canonical person, consented).
2. **The gateway** — every call passes the wall; RBAC/ABAC scoped; schema-validated; audited.
3. **The event seam** — modules emit up, read governed views down.

Surfaces reach modules through gateway'd APIs. Modules reach intelligence through events. Vidya reaches across by calling capabilities. That single circuit — identity → app → capability → event → intelligence → recommend → approve → execute → outcome → learn — is the whole platform.

## The secure-core boundary

**Inside the wall (founder + Claude Code only):** identity, consent, gateway policy, the event/evidence contract + store, the evidence/mastery/gap engines (the IP, and the place a wrong judgment is existential), the AI fabric router + agents + verification substrate, governance/audit/secrets.

**Outside the wall (developer lanes, against contracts, no credentials, no platform store, reviewed + scrubbed):** role surfaces, non-sensitive module logic, integration adapters. They consume the API; they never build the orchestrator or the agents.

## The three rings (priority)

- **Ring 0 — base:** operational data substrate, identity & gateway, the immutable event store + event/evidence contract, secrets + CI/CD.
- **Ring 1 — first-slice enablers:** the AI fabric router (thin, two-track slot, Langfuse), the workflow + permission-ladder runtime, the content generate-verify substrate, the evidence/mastery/gap engines — each only as deep as the Student ⇄ Teacher slice forces.
- **Ring 2 — intelligence and scale:** full platform intelligence (profile, graph, feature store, prediction), FLUID connectors, comms lifecycle, analytics and experimentation depth, Track 2 models, multi-tenancy across group/franchise/programme/network.

The event contract is Ring 0 even though the intelligence that consumes it is Ring 1–2. Emit from line one, consume as it matures.
