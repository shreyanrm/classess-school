# Content & resources (module B3)

The content library, generated supporting material, and the human verification
surface. Content is GENERATED against the ontology and VERIFIED before use —
nothing unverified is served (INVARIANT 7). Generation wires to the ai-fabric
generate-and-verify substrate (`spine/ai-fabric`); this module never
re-implements the confidence gate, it delegates to it and honours its verdict.

This package is deterministic-first and import-safe. It depends only on the
standard library plus the ai-fabric spine (itself standard-library-only on the
deterministic paths). No live LLM key, no Supabase, no OCR provider is required
for the deterministic paths or the tests. It does not modify the spine.

## Surfaces

- **`repository.py`** — the content metadata repository keyed to ontology topics.
  - VERSIONING: every change appends an immutable `ContentVersion`; history is
    never rewritten. A new version after approval returns the record to review
    and withdraws the live pointer.
  - APPROVAL STATE: `DRAFT -> IN_REVIEW -> APPROVED / REJECTED / RETIRED`. Only
    an APPROVED record with a live, verified version `is_servable`. The
    repository refuses to make an unverified version live.
  - LICENCE METADATA: `LicenceMetadata` carries provenance, holder, licence
    code and attribution so nothing is served without clear rights.
  - SEMANTIC SEARCH: `PgVectorSearchIndex` (production pgvector cosine query)
    and `InMemorySemanticSearchIndex` (the deterministic offline fallback) share
    one interface. `search(..., only_servable=True)` keeps drafts out of learner
    results by construction.

- **`generate.py`** — generate explanations, worked examples, and practice items
  for a topic via the ai-fabric orchestrator. Only content whose verification
  block reports `served` is returned as `GeneratedMaterial`; a withheld result
  is a refusal carrying the review reason. `generate_into_repository` files a
  DRAFT — never auto-published (the permission ladder; agents prepare, humans
  approve).

- **`ingest.py`** — the upload/ingest interface (OCR / transcription /
  document-understanding). Providers are interfaces with `Null*`
  graceful-degradation implementations that report unavailable rather than
  fabricating text. Ingest produces UNVERIFIED DRAFT metadata only; promotion is
  a human act through the verification surface.

- **`verification_surface.py`** — the confidence-banded human review queue data
  shapes. GREEN / AMBER / RED is a triage hint for reviewer attention; it never
  promotes content on its own. An explicit human `ReviewDecision` of `APPROVE`
  is the permission-ladder act that promotes a record, and the repository still
  refuses to serve an unverified version.

## How verification flows (INVARIANT 7)

1. `ContentGenerator.generate` builds an ai-fabric `Intent` and calls the spine
   `Orchestrator`, which routes on the owning track, runs deterministic checks
   FIRST (the spine's real `ast`-based arithmetic verifier for math/physics),
   then a second-model cross-check, then the confidence gate.
2. With no live provider the second model abstains, so narrative material is
   refused (never fabricated) and deterministically-correct math items are
   withheld until a second model agrees — proving the gate is honoured, not
   bypassed.
3. Served material is filed as a DRAFT and enqueued for human review. Approval
   promotes it; the repository refuses to make an unverified version live.

## Env vars (names only — INVARIANT 4)

Secrets are environment-only, read by NAME, never hardcoded. Names follow
`clss.<app>.<env>.<purpose>`, mapped to an OS env key by uppercasing and
replacing `.`/`-` with `_`. No key value appears in this repository; absence
degrades to a clearly-marked unavailable/refusal.

| Secret name (dotted)                          | OS env var                              | Purpose                                       |
| --------------------------------------------- | --------------------------------------- | --------------------------------------------- |
| `clss.content.dev.pgvector_dsn`               | `CLSS_CONTENT_DEV_PGVECTOR_DSN`         | Postgres/pgvector DSN for the content library |
| `clss.content.dev.embedding_provider_key`     | `CLSS_CONTENT_DEV_EMBEDDING_PROVIDER_KEY` | Embedder key for semantic search            |
| `clss.content.dev.ocr_provider_key`           | `CLSS_CONTENT_DEV_OCR_PROVIDER_KEY`     | OCR provider for image/PDF ingest             |
| `clss.content.dev.transcription_provider_key` | `CLSS_CONTENT_DEV_TRANSCRIPTION_PROVIDER_KEY` | Speech-to-text for audio/video ingest   |
| `clss.content.dev.doc_understanding_key`      | `CLSS_CONTENT_DEV_DOC_UNDERSTANDING_KEY` | Layout/structure understanding              |

The LLM provider key for generation is owned and named by the ai-fabric router
(`clss.aifabric.dev.track1_provider_key`); this module holds no credentials of
its own.

## Tests

`tests/` covers versioning, the approval lifecycle (including the refusal to
approve an unverified version), licence metadata, in-memory and pgvector search
surfaces, the served-vs-withheld generate path, the deterministic math verifier,
ingest graceful degradation, confidence banding, and the human-approval
permission ladder. Import-safe, no network, no secrets.

```
python -m pytest modules/content
```
