# Build flow — what is built, in what order, how

## The unit of work

The **vertical slice**: one capability cut down through the spine and up to the surfaces that touch it, emitting events, governed. You never build a module or a surface to completion in isolation — you build slices. Structure says where things live (`03`); this file says in what order and how.

## Ring 0 — the base (build first, completely, serially)

Steps from `07-ring0-build-brief.md`:

```
repo + secrets + CI  →  /contracts  →  data substrate  →  identity  →  gateway  →  event store
```

**Checkpoint 0:** pass the Ring 0 done-line, stop, report. The base exists. The `/contracts` package now unblocks the developer team.

## Ring 1 — the academic loop (slices, in order)

### Slice 1 — Student ⇄ Teacher core loop (both surfaces together; the heart)

```
teacher assigns / assesses
  → student attempts  (independent vs supported captured)
    → event emitted
      → evidence weighted  (Performance × Reliability × Independence × Difficulty × Recency × Consistency)
        → gap classified  (one of ten types)
          → intervention fired
            → reassess unaided
              → mastery updates  (only on fresh evidence)
                → teacher sees it
```

Both surfaces are the two ends of one loop — neither is testable without the other, so they are built together, not sequentially. Lights up: B6 Coursework & assessment + the evaluation engine, B7 Learning, A3 evidence/mastery/gap engines, B3 content generate-verify, A5 workflow/permission runtime, A4 AI fabric router. Built to production depth on a narrow path first — one board, one grade, two subjects — board-agnostic in the contract, proven narrow.

**Checkpoint 1:** the loop runs end to end on real evidence. Report.

### Slice 2 — Admin (full)

Now evidence flows up. Mastery heatmaps, gap trends, intervention effectiveness, multi-branch leadership views, the role permission matrix, the proactive feed. Completes B1 Institution & policy and B2 Scheduling & continuity.

**Checkpoint 2:** report.

### Slice 3 — Parent

The absolution engine + consent authority: the child view, the weekly proof artifact, learn-alongside, PTM. Consumes B8 learner record + the consent service. Built after the loop because it is a near-pure consumer — earlier, it is a beautiful empty room.

**Checkpoint 3:** report.

(B9 Communication, B10 Teacher growth, and B11 Intelligence views deepen across these slices.)

## Ring 2 — intelligence and scale

Full platform intelligence (profile, graph, feature store, prediction); A6 FLUID connectors and the integration hub; comms lifecycle at full strength; analytics/experimentation depth; Track 2 models filled into the router slot; multi-tenancy across group / franchise / programme / network.

## The critical path

```
secrets + CI → data + contracts + identity → gateway → event store
  → Student ⇄ Teacher loop → (Admin ∥ Parent) → Ring 2
```

## Parallelization (once contracts land)

- **Claude Code agents (secure core):** identity, gateway policy, event store, the evidence/mastery/gap engines, the AI fabric router, the verification substrate — each in its own git worktree.
- **Developer lanes (surfaces + non-sensitive modules, against contracts):** frontend builds the role screens, backend builds non-sensitive module logic, integrations build adapters — mocking anything not yet live.
- The **contract boundary** is the integration point. The seam that makes the architecture safe is the seam that makes the parallelism safe: agents on disjoint modules behind shared contracts run clean; agents on the same files collide.

## How each piece is built (the loop)

```
plan the slice + its contracts
  → spawn agents per bounded context in worktrees
    → emit attributed events
      → verify  (invariants, confidence gate, contract holds, tests)
        → integrate at the contract boundary
          → confidentiality-scrub
            → merge
              → checkpoint report
```

Serial where it must be (Ring 0 settles before slices); parallel where it can be (core engines and dev lanes on disjoint modules once contracts exist). Stop and report at every ring and slice boundary — human authority gates the boundaries.
