# Classess School — Learning module (B7)

The learner-facing adaptive loop. Learning is **pose -> struggle -> reveal**,
never explain-first. Practice contributes **evidence, not a completion tick**.
The assistance ladder **fades** as competence grows. Spaced retrieval runs
against the **real forgetting curve**.

This is a capability module (B7). It does **not** author mastery — the
evidence/mastery/gap judgment is CORE and lives in the intelligence engine
(spine A3, consumed read-only). This module orchestrates the flow and **emits
evidence events** keyed to the opaque `canonical_uuid` only.

## What it owns

| File | Responsibility |
| --- | --- |
| `learn.py` | The pose -> struggle -> reveal flow controller. Poses a problem, gives room to struggle, and **refuses a reveal/scaffold until a genuine attempt** (the anti-explain-first guard). Records whether help was used, which sets the keystone independent-vs-supported flag on the resulting attempt. |
| `practice.py` | Adaptive next-item selection by **mastery + gaps** (mistake-based). The gap **type** shapes the item — each of the ten gap types calls for a distinct response, never generic "more questions". Difficulty is matched just beyond what the learner can do alone; the assistance rung is the faded rung. |
| `ladder.py` | The assistance-ladder controller: `Learn -> Coach -> Hint -> Work-with-me -> Check-my-work -> Independent`. Fades support one rung at a time as mastery rises, steps it back up on a fresh struggle, gates the `Independent` rung on the independence floor, and **always declares helping vs evaluating**. |
| `revision.py` | Spaced-retrieval scheduler against an exponential forgetting curve. Stability grows with each spaced, **independent** success (the spacing effect) and resets on a failed recall. Revision is "due" when predicted retention falls to the target retrievability. |
| `readiness.py` | Exam-readiness forecasting from **mastery + coverage**. Leans on the Independence dimension (an exam is unaided), discounts decayed (revision-due) topics and confirmed gaps, and surfaces a plain-language verdict plus the topics that carry the risk. |
| `events.py` | Emits `attempt.recorded` evidence events behind the contract shapes — carrying the keystone independent-vs-supported `mode` and the assistance level used. Append-only; PII-free; every write passes the gateway. |

## Invariants honoured

- **Opaque identity only (INVARIANT 1 + 2).** Every event and projection is keyed
  by `canonical_uuid` + opaque ontology ids. No builder accepts a name/email.
- **Append-only events (INVARIANT 5).** The emitter only appends; it never
  updates or deletes. The contract envelope has no mutation path.
- **Every cross-service call passes the gateway.** Event egress is never direct;
  with no gateway configured, emission degrades to a labelled in-memory
  append-only sink.
- **Secrets are env-only (INVARIANT 4).** Config is read from the environment by
  name. No secret value is hardcoded, defaulted to a literal, or invented.
- **Agents hold no credentials (INVARIANT 8).** No auth token is constructed from
  a literal anywhere; a real sink reads its token from the environment by name.
- **Mastery is never authored here, never collapsed for a learner.** The CORE
  engine owns the six-dimension reading; surfaces show plain language
  ("you can do this independently" / "you can do this with guidance" /
  "revision is due"), never the formula or a raw number.
- **A judgment is never confirmed from a single bad score.** Practice and
  readiness act on the engine's **confirmed** gaps; unconfirmed signals never
  block or down-rank.

## Degrades gracefully (no live provider yet)

There are **no live LLM keys or Supabase** wired. The module degrades behind
clear interfaces:

- The CORE intelligence engine (`spine/intelligence`) is consumed through
  `_engine.py`. If it (or its `pydantic` dependency) is unavailable,
  `_engine.available()` is `False` and the flows fall back to deterministic,
  dependency-free heuristics over plain per-topic state — clearly labelled.
- Event emission degrades to an in-memory append-only sink when the gateway +
  sink are unset; emitted events are reported as `delivered = False` so the
  caller knows they are local only.
- The deterministic paths produce the same result with or without a provider.

Everything is **import-safe**: importing the package performs no I/O, opens no
connection, and reads no secret value.

## Environment variables (names only — INVARIANT 4)

Read by name, never hardcoded. Dotted names map to `CLSS_LEARNING_DEV_*`
(uppercase, dots -> underscores). `LearningSettings.degraded_reasons()` returns
the **names** (never values) of the vars whose absence keeps the module degraded.

| Dotted name | Maps to | Purpose |
| --- | --- | --- |
| `clss.learning.dev.gateway_url` | `CLSS_LEARNING_DEV_GATEWAY_URL` | The only egress. Every cross-service call (event sink, ontology, remote engine) passes the gateway. **Unset -> degraded.** |
| `clss.learning.dev.event_sink_url` | `CLSS_LEARNING_DEV_EVENT_SINK_URL` | Where evidence events are POSTed (through the gateway). **Unset -> in-memory append-only sink.** |
| `clss.learning.dev.database_url` | `CLSS_LEARNING_DEV_DATABASE_URL` | The read store the intelligence engine replays. **Unset -> in-memory replay.** |
| `clss.learning.dev.crosscheck_model_key` | `CLSS_LEARNING_DEV_CROSSCHECK_MODEL_KEY` | Reserved name for a future second-model verification cross-check (generate-and-verify, INVARIANT 7). **No value is ever stored here.** |

## Running the tests

Pure stdlib; the deterministic paths need no provider and no build step. The
engine-integration tests require the spine engine (and its `pydantic`
dependency) and **skip cleanly** when it is absent.

```
pip install pytest pydantic   # only to exercise the engine-integration path
pytest
```

The suite exercises: the reveal is refused before a genuine attempt; help-used
sets the supported flag and an unaided solve is `Independent`; support fades a
rung at a time and steps back up on struggle; each gap type maps to a distinct
practice response; spaced independent successes grow memory stability and a
failed recall makes revision due now; readiness discounts supported-only mastery
and unknown coverage; emitted events are coherent, PII-free, and append-only.
```
