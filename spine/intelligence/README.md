# Classess Intelligence Engine (spine A3, Ring 1)

The evidence -> mastery -> gap projection engine. It computes derived learner
state by **replaying** the immutable event log — it never authors mastery
directly. Pure, deterministic, no external calls: the same events in always
yield the same reading out, which is what lets "understanding of every past
learner improve as the models improve" (re-run a new model over the old events).

Mirrors the event/evidence contract in `contracts/src/events/*` (the attempt
event with its independent-vs-supported flag, the six mastery dimensions, the ten
gap types, the `GapEvidence` lineage envelope) and the prerequisite graph in
`contracts/src/ontology/*`.

This is `CORE`, where a wrong learner judgment is existential. Two CORE
guarantees are enforced in code and exercised by the tests:

- **Mastery is never an average and never an opaque number for a learner.** Six
  explicit dimensions, a multiplicative composite, a plain-language band.
- **A gap is never confirmed from a single bad score.** Confirmation requires at
  least two corroborating signals (or a reassessment); one bad score is an
  unconfirmed prompt-to-reassess, never a judgment.

## The model

```
Mastery = Performance × Reliability × Independence × Difficulty × Recency × Consistency
```

A **product**, not a sum. A near-zero on any one dimension caps the whole
reading. That is the design intent: a learner who only performs **with help**
(Independence near zero) cannot read as a master no matter how high their raw
success rate.

### The six dimensions (`mastery.py`)

Each is computed in `[0,1]` from one learner's replayed attempt history for one
topic, recency-weighted, then combined as `∏ dimension^weight`
(`MASTERY_WEIGHT_MODE = "multiplicative"`; weights are exponents, uniform by
default, tunable behind the contract without changing its shape).

| Dimension | What it reads |
| --- | --- |
| Performance | Recency-weighted success rate — the starting point. |
| Reliability | Dependability across attempts; ramps with corroborating count, pulled down by variance. A single observation is inherently unreliable. |
| **Independence** | The keystone. The recency-weighted share of **successful** performance produced **independently**. All-supported success -> near 0; all-independent success -> ~1. Partial ladder credit for near-independent rungs. |
| Difficulty | Difficulty of items **succeeded** on — easy wins weigh less than hard ones. |
| Recency | Freshness of the evidence (exponential half-life decay); links to the retention gap. |
| Consistency | Stability over time — a steady/improving curve reads high, oscillation reads low. |

### Independent vs supported — the keystone

The attempt event's `mode` (`independent` / `supported`) and `assistance_level`
(`Learn -> Coach -> Hint -> Work-with-me -> Check-my-work -> Independent`) are
the single most important bits in the evidence layer. The Independence dimension
is the only place that separates "can do alone" from "only with help"; without
it mastery degenerates into an average and the platform's core claim collapses.

### Plain language for learners (never the formula)

A learner **never** sees the formula, the composite number, or the dimension
names. `MasteryResult` carries the structured `MasteryReading` (for surfaces and
ranking) **and** a `plain_language` string — one of:

- "you can do this independently"
- "you can do this reliably, with a little support"
- "you can do this with guidance"
- "you are starting to see how this works"
- "revision is due" (retention override when recency has decayed)
- "not started yet"

Bands are guarded: no amount of supported success reaches `secure`/`independent`
(Independence collapses the product), and a single observation never reads above
`developing`.

## The ten gap types (`gaps.py`)

Each gap type needs a **different** response, so each has its own detection rule
reading the evidence trail (and, for prerequisite gaps, the **confirmed**
prerequisite graph). Collapsing every struggle into one "struggling" signal is
exactly what this taxonomy prevents.

| Gap | Detection rule (summary) |
| --- | --- |
| prerequisite | Weak here **and** weak on a confirmed prerequisite topic -> route back to the prerequisite. Unconfirmed (proposed) edges never drive this. |
| conceptual | Fails even with support, scores near zero — the idea is wrong, not the execution. |
| procedural | Partial credit / coachable but not reliably executed alone. |
| application | Succeeds on easy items, fails on harder/novel ones — does not transfer. |
| retention | Real earlier success, now decayed (recency low). Distinct from never-learned. |
| language | Slow **and** wrong even on easy items. Conservative: **proposed only**, never confirmed without a richer free-text/translation signal. |
| accuracy | Method right, error-prone slips (near-misses), fast. |
| speed | Correct and accurate but consistently too slow for the timed context. |
| confidence | Capable with light support but dips under full self-reliance. |
| support-dependency | Strong only when supported, no independent transfer — the gap the Independence dimension exists to surface. |

**No single-score confirmation.** `MIN_SIGNALS_TO_CONFIRM = 2`. `GapEvidence.confirmed`
is true only at/above that floor; otherwise the gap surfaces as a low-confidence,
unconfirmed signal. Speed vs accuracy are deliberately distinguished (slow-correct
vs right-method-with-slips).

The optional second-model cross-check (generate-and-verify, INVARIANT 7) is named
but **absent** here — the deterministic rules stand on their own and refuse to
over-claim (e.g. language stays unconfirmed) until a richer signal is wired.

## The lineage guarantee (`evidence.py`)

Every conclusion is traceable. `EvidenceItem` keeps a back-reference to its
source `event_id`; every `MasteryResult` carries `evidence_event_ids` and every
`GapEvidence` carries `evidence_event_ids` + a plain-language `rationale`. No
mastery reading and no gap is ever an opaque claim — it names the rows that
produced it.

`evidence.py` also owns the **weighting** (recency half-life decay, mode,
assistance level, evaluator-confidence band) and the **freshness guard**: the
profile updates **only** when new events have arrived since the last projection
(`has_fresh_evidence`), so a rebuild is a no-op for an unchanged topic and a stale
read can never re-confirm a gap.

## Projections rebuild from events (`profile.py`, `graph.py`)

Derived stores are projections, never authored directly.

- `build_profile(events, subject=...)` -> a `LearnerProfile`: per touched topic,
  the mastery reading + detected gaps, each with lineage. Rebuilding from the
  same event list yields an identical profile — **idempotent by construction**.
  With `previous` + `last_projected_at`, topics with no fresh evidence are
  carried over unchanged.
- `build_learner_graph(events)` -> a `LearnerGraph`: the cohort view — every
  learner's profile plus governed roll-ups (per-topic band distribution,
  confirmed-gap counts, the set of learners with a confirmed gap of a given type
  on a topic). The proactive layer (A5/B7) acts on those sets **behind the
  permission ladder** — never here.

Everything is keyed by the opaque `canonical_uuid` and opaque ontology ids only
(INVARIANT 1 + 2 — no PII, ever). Consent/purpose gating is applied at **read
time** by the event store's governed read functions; this engine assumes it was
handed an already-gated event list and adds no identity beyond the opaque token.

## The event source — degrades gracefully (`source.py`)

The engine reaches the immutable event store + ontology service **through the
gateway** (every cross-service call passes the gateway). It holds **no
credentials** (INVARIANT 8) and makes no network call itself.

`EventSource` is the read-only interface. When no provider is configured the
engine returns `InMemoryEventSource` — explicitly labelled **degraded** — and the
pure projection paths produce identical results either way, which is what keeps
rebuilds reproducible and the test suite offline.

## Environment variables (names only — secrets are env-only, INVARIANT 4)

Read by name, never hardcoded. Dotted names map to `CLSS_INTELLIGENCE_DEV_*`.

| Dotted name | Maps to | Purpose |
| --- | --- | --- |
| `clss.intelligence.dev.database_url` | `CLSS_INTELLIGENCE_DEV_DATABASE_URL` | The event source to replay. **Unset -> degrade to the in-memory event list.** |
| `clss.intelligence.dev.gateway_url` | `CLSS_INTELLIGENCE_DEV_GATEWAY_URL` | The only egress; the event store + ontology are read through it. |
| `clss.intelligence.dev.crosscheck_model_key` | `CLSS_INTELLIGENCE_DEV_CROSSCHECK_MODEL_KEY` | Reserved name for a future second-model gap cross-check (INVARIANT 7). No value is ever stored here; the deterministic rules work with no provider. |

`settings.degraded_reasons()` returns the **names** (never values) of the vars
whose absence keeps the engine degraded.

## Layout

```
app/
  config.py     pydantic-settings; env-only secrets; degraded-reasons reporting
  models.py     pydantic mirrors of the event/evidence + ontology contracts
  evidence.py   EvidenceItem, weighting, freshness guard, lineage
  mastery.py    the six dimensions, multiplicative composite, plain-language bands
  gaps.py       the ten gap rules; never-confirm-from-one-score
  profile.py    per-learner projection; idempotent rebuild; fresh-evidence guard
  graph.py      cohort learner-graph projection + governed roll-ups
  source.py     EventSource interface + in-memory degraded source
tests/          synthetic-event suite (import-safe, offline, deterministic)
```

## Running the tests

Pure stdlib + pydantic; no network, no provider, no build step required.

```
pip install -r requirements.txt   # pydantic, pydantic-settings, pytest
pytest
```

The suite exercises the loop end to end: independent vs supported changes the
result; a single bad score does **not** confirm a gap; a reassessment lifts
mastery and clears the gap; proposed (unconfirmed) prerequisite edges never drive
a routing judgment; projections rebuild idempotently from the event list.
