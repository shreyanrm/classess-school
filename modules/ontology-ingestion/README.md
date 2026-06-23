# Classess School — Curriculum & ontology ingestion (A2, Ring 1)

A2's ingestion pipeline over the board-agnostic ontology contract. The seed
ontology lives in `contracts/src/ontology`
(board → grade → subject → unit → chapter → topic → outcome → competency, plus a
prerequisite `Edge` and a `CrossBoardEquivalence`). This module ingests
curriculum **into** that graph, stewards its prerequisite edges, maps equivalence
across boards, and indexes nodes semantically.

Three laws run through every surface here:

- **Board-agnostic.** A board is a labelled node, never a baked-in enum. The
  same pipeline ingests any board; nothing about a board is hard-coded.
- **Prerequisite edges are an owned, expert-validated artifact.** The steward
  **proposes** edges; only a human steward's confirmation makes an edge trusted
  for routing. A proposal is never auto-trusted.
- **Generate-and-verify with a confidence gate.** Ingested nodes are **drafts**;
  proposed edges and proposed equivalences are **candidates**. Promotion to a
  trusted artifact is always a separate, explicit human act.

## What it owns

| File | Responsibility |
| --- | --- |
| `app/ingest.py` | Ingests curriculum from documents / standards / publisher content into the ontology graph. The **document-understanding** step is an interface (`DocumentUnderstanding` Protocol) that **degrades gracefully**: with no provider, `NullDocumentUnderstanding` reports unavailable and ingestion uses the structured-source path or records **pending extraction** — it never invents extraction output. Maps each outline node onto its typed ontology table under its parent. Applies the confidence gate (a node below it is flagged `needs_review`). Deterministic, idempotent node ids. |
| `app/steward.py` | The **prerequisite-edge steward**. Proposes candidate edges from curriculum order and (optionally) semantic similarity; every proposal starts `confirmed = False`. `confirm(...)` requires an explicit opaque **steward ref** (it refuses without one) and is the only path into `trusted_edges()`. `reject(...)` likewise needs a steward ref. Decisions are an append-only log. |
| `app/equivalence.py` | **Cross-board equivalence** mapping — **symmetric** and **board-agnostic** (every board is a code label). Adding A≡B makes B≡A discoverable with the same confidence. `propose(...)` records an unconfirmed candidate; `confirm(...)` makes it trusted. Confidence-gated lookups. |
| `app/embeddings.py` | The **pgvector semantic-index interface** with an **in-memory fallback**. `Embedder` + `VectorIndex` Protocols; offline defaults are a deterministic `HashingEmbedder` and an exact `InMemoryVectorIndex`. The external (Track 1) and proprietary/edge (Track 2) model lanes are **separate** env vars selected by a router — never blended. |
| `app/events.py` | Emits `ontology.node_ingested`, `ontology.edge_proposed`, `ontology.edge_confirmed`, and `ontology.equivalence_mapped` on the attributed, append-only event envelope (`operations` purpose). Opaque ids only; `ontology.edge_confirmed` refuses to record a confirmation without a steward ref. |
| `app/seed.py` | A Python view of the Slice 1 seed snapshot, mirroring the contract with the same stable ids (for tests and projections). |
| `app/config.py` | Env-var **NAMES only**. Degrades gracefully when nothing is set. |
| `app/_ontology.py` | The Python shape of the ontology contract types (board → … → competency, `Edge`, `CrossBoardEquivalence`). |

## Invariants honoured

- **Opaque identity only.** Every node, edge, equivalence, and event is keyed by
  opaque ids; behavioural data carries only `canonical_uuid`. No builder accepts
  a name/email; ontology metadata carries no PII.
- **Prerequisite edges never auto-trusted (permission ladder).** Confirming an
  edge is consequential and requires a human steward ref. `trusted_edges()`
  returns confirmed edges only; the steward never self-confirms.
- **Append-only events.** The emitter only appends; it never updates or deletes.
- **Every cross-service call passes the gateway.** Document understanding,
  pgvector, and event egress are never direct; with no gateway + provider
  configured each degrades to a clearly-labelled in-memory / offline path.
- **Track separation.** Track 1 (external) and Track 2 (proprietary/edge)
  embeddings lanes are distinct env-var names and never merged into one key.
- **Secrets are env-only.** No secret value is read at import or stored as a
  literal; only the dotted NAMES below are referenced. No `NEXT_PUBLIC_` secret.

## Configuration (environment variable NAMES only)

Dotted convention `clss.<app>.<env>.<purpose>`; the OS key is the dotted name
uppercased with dots/dashes → underscores (e.g.
`clss.ontology.dev.gateway_url` → `CLSS_ONTOLOGY_DEV_GATEWAY_URL`). All are
optional; absence keeps the module in deterministic, offline mode.

| Dotted name | OS env var | Purpose |
| --- | --- | --- |
| `clss.ontology.dev.gateway_url` | `CLSS_ONTOLOGY_DEV_GATEWAY_URL` | The only egress. Every cross-service call passes the gateway. |
| `clss.ontology.dev.event_sink_url` | `CLSS_ONTOLOGY_DEV_EVENT_SINK_URL` | Where emitted ontology events are POSTed (through the gateway). |
| `clss.ontology.dev.database_url` | `CLSS_ONTOLOGY_DEV_DATABASE_URL` | The operational store for ontology rows. |
| `clss.ontology.dev.pgvector_url` | `CLSS_ONTOLOGY_DEV_PGVECTOR_URL` | The pgvector-backed semantic index. Unset → in-memory fallback. |
| `clss.ontology.dev.doc_understanding_key` | `CLSS_ONTOLOGY_DEV_DOC_UNDERSTANDING_KEY` | The document-understanding (curriculum extraction) provider. Unset → draft / structured-source only. |
| `clss.ontology.dev.embeddings_track1_key` | `CLSS_ONTOLOGY_DEV_EMBEDDINGS_TRACK1_KEY` | Track 1 (external) embeddings model lane. |
| `clss.ontology.dev.embeddings_track2_key` | `CLSS_ONTOLOGY_DEV_EMBEDDINGS_TRACK2_KEY` | Track 2 (proprietary/edge) embeddings model lane — kept separate from Track 1. |

No secret VALUE is ever hardcoded. The gateway bearer token and any provider key
are read from the environment by name at the point of egress (not implemented
while no provider exists); never exposed to the browser, never a `NEXT_PUBLIC_`
var.

## Tests

```
pytest          # from this directory
```

Import-safe and offline: the whole suite runs with no network, no DB, and no
provider, exercising the deterministic (degraded) paths — the supported paths
until the gateway, document-understanding provider, pgvector index, and event
store are wired.
