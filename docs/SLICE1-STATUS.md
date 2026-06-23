# Slice 1 — Checkpoint 1 status

The Checkpoint 1 question is: **does the Student ⇄ Teacher loop run end to end on
real evidence?** It does — live and deterministic in the browser at `/loop`, over
real attempt events, through a faithful port of the spine intelligence engine.
Code-shaped work is complete and production-grade; the items that need a live LLM
provider (through the gateway) or a live Supabase event store are correct in
source and gated behind named env vars, awaiting provisioning before the slice
widens beyond the narrow path.

---

## Does the loop run end to end?

Yes. Each step of the loop is exercised, on real (not faked) data:

| Loop step | Where it runs | Status |
|---|---|---|
| Teacher assigns / assesses | `surfaces/web` `/teacher/assign`, `/teacher/evaluate`; `modules/coursework` | done — runs in-browser; Prepare → Approve gate never auto-sends |
| Student attempts, independent vs supported captured | `surfaces/web` `/student/learn`; `modules/learning` `learn.py` | done — the flag is set at the act, not inferred |
| Attempt event emitted (immutable) | `modules/coursework`/`learning` `events.py`; event store (Ring 0) | done in-engine; live append to the store is pending-provisioning |
| Evidence weighted, six dimensions | `spine/intelligence` `mastery.py`/`evidence.py`; web `lib/engine.ts` | done — multiplicative composite, recency-weighted |
| Gap classified, one of ten types | `spine/intelligence` `gaps.py`; web `lib/engine.ts` | done — ten distinct rules; ≥ 2 signals to confirm |
| Intervention fired (recommend, never auto-fire) | `spine/workflow`; web `/loop`, `/teacher` | done — full provenance, Approve · Adjust · Decline |
| Reassess unaided | `modules/learning` `ladder.py`; web `/loop` | done — the Independent rung is the only evaluating rung |
| Mastery updates on fresh evidence only | `spine/intelligence` `profile.py`; web `lib/engine.ts` | done — freshness guard carries unchanged topics |
| Teacher sees it (plain language) | `surfaces/web` `/teacher/students`, `/loop` | done — six-dimension drawer, gap chips, no raw score |

The two correctness laws hold and are exercised: independent vs supported changes
the reading; a single bad score never confirms a gap; a reassessment lifts mastery
and clears the gap.

---

## What is production-grade now

- **The CORE engines.** The six-dimension multiplicative mastery model, the ten
  gap-type rules, evidence weighting, and idempotent profile/graph rebuilds in
  `spine/intelligence` — and the same logic ported faithfully into the web
  `lib/engine.ts` and verified against the Python rules. No averages, no opaque
  number to a learner.
- **Generate-and-verify with the confidence gate (INVARIANT 7).** A real
  deterministic arithmetic/expression verifier on a safe AST evaluator; the gate
  serves only when deterministic checks pass AND a second model agrees AND
  confidence ≥ threshold. Coursework paper generation and content generation both
  consume it; withheld items are flagged for human review, never served.
- **The permission ladder and human-final marking (INVARIANT 8).** Every
  consequential action (send/submit/publish/delete/charge/grade) is pinned to
  execute-with-permission and can never be safe-automatic; `execute()` returns a
  clearance, never a side effect; agents hold no credentials. The coursework
  marking gate forces MIDDLE/LOW bands to human review and refuses a final
  consequential mark without `human_confirmed`; poor handwriting never reduces a
  mark.
- **The two-track router (INVARIANT 11).** Track 1 and Track 2 are distinct config
  structures with distinct env names; selection never crosses tracks. Track 2 is a
  config-only enable path, no re-architecture.
- **The surfaces.** Both ends on the v4 design system; all twelve routes return
  200; `tsc --noEmit` passes; every page ships empty / loading / error states.
  Learner-facing surfaces never render a raw score, the composite, or the formula.
- **Confidentiality.** No codenames, no real personal or board names (generic
  `Student A` / `Class 10-B`, neutral example board), no real pricing, no emoji, no
  exclamation marks in product copy, across every artifact.

---

## What remains pending live provisioning

The deterministic paths run today with no provider. The following are correct in
source and gated behind named env vars; they must be provisioned (founder) and
installed/built centrally (orchestrator) before going beyond the narrow path.

1. **Live LLM provider via the gateway (Track 1).** The ai-fabric router reads
   `clss.aifabric.dev.track1_provider_key` by name; absent, it returns a clean
   unavailable result and never fabricates. Until a key is live, narrative
   generation is refused and the objective evaluation path with a correct
   deterministic answer lands at MIDDLE + needs_review (not HIGH) — the engine never
   stands alone without the second-model cross-check. A live second model lets it
   reach HIGH / provisional-auto.
2. **The Supabase event store (and pgvector).** Event emission currently degrades
   to an in-memory append-only sink; the intelligence engine reads from an in-memory
   source. Wiring the event store (immutable, consent-gated reads) and pgvector for
   content semantic search is pending-provisioning behind the named DSN/URL env vars.
3. **Ingestion providers.** OCR, transcription, and document-understanding are
   interfaces with `Null*` degraders that report unavailable rather than inventing
   text; live keys are named but not yet supplied.
4. **The Python test suites at runtime.** pydantic / pydantic-settings / pytest are
   not installed in the current environment and installs were forbidden, so the
   suites were verified by clean byte-compile plus stdlib smoke harnesses that
   exercise the load-bearing logic (the confidence gate, the permission classifier,
   the originality bands, the deterministic verifier). Run them with the per-package
   `pip install -r requirements.txt && pytest` recipes in `docs/SLICE1.md` once the
   deps are present.
5. **The contracts `dist/` rebuild.** The published `dist/` is pre-Slice-1; the web
   surface resolves the contracts source directly via a webpack extension alias. A
   central `npm run build:contracts` will refresh `dist/` for downstream consumers.

---

## The narrow path, and widening from it

The slice is proven on one example board, Class 10, Mathematics and Physics — by
design, to prove depth before breadth. The board is a labelled ontology node, not
an enum of permitted boards, and the curriculum is mapped, never hard-coded; the
mastery and gap engines, the evaluation modes, and the assistance ladder are all
board-agnostic. Widening to more grades, subjects, and boards adds ontology nodes
and content; it does not change the shape of the contract or the engines.

The next slices (Admin, then Parent) consume the evidence this loop produces; with
Checkpoint 1 cleared and live provisioning wired, the platform moves to
Slice 2. See `docs/SLICE1.md` for the full build and `05-build-flow.md` for the
slice order.
