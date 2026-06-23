# Model foundry (spine A4 — the Track 2 BASE)

The continuously-learning pipeline that turns everything happening in the
application into LEARNING SIGNALS and, when compute is attached, distils a small
proprietary edge **student** model that fills the reserved **Track 2** slot in
the AI fabric.

This module is production-grade **scaffolding**: real, tested code for the whole
closed loop **except** the actual GPU training, which is an injected backend that
degrades to a clearly-marked `no-compute` plan when no training endpoint is
configured. It never fabricates a model.

## The loop

```
observe(events)
  -> capture            events -> learning signals (input, output, reward, task_class),
                        keyed by opaque canonical_uuid, consent-stamped (NEVER PII)
  -> consent-gate       keep ONLY admissible signals (deny-by-default; minors restricted;
                        revocation removes a learner's contributions)
  -> curate             safety + generate-and-verify + balance; only verify-passing
                        outputs become positive targets; unsafe/low-confidence/
                        contradictory dropped
  -> dataset            versioned, deduplicated, PII-scrubbed; train/val/test splits;
                        full provenance + content hash; reproducible
  -> (train backend)    distil a Track-1 frontier TEACHER into a Track-2 edge STUDENT;
                        no-compute plan by default — never fabricates a model
  -> eval               scorecard on held-out sets AND platform-meaningful metrics,
                        comparable vs the incumbent
  -> require_approval    permission ladder — promotion is CONSEQUENTIAL; never auto-fires
  -> promote            ONLY on explicit human approval -> advances into the Track 2 slot
  -> serve(Track 2)      the promoted student serves the high-frequency "ocean"
  -> observe outcomes    new events feed the next turn
```

`loop.py` is pure orchestration over the above; it is **idempotent and
replayable** — the dataset content hash is a pure function of the admissible
signals, so re-running `observe` over the same events yields the same dataset id
and the same candidate plan. Promotion is the only side-effecting, human-gated
step.

## Relationship to Track 2 (do not conflate the two tracks)

The foundry only ever produces **Track 2** students (`track == 2` everywhere).
The TEACHER is a Track-1 frontier model **label** used as a distillation source
only — no Track 1 credential is read here. The fabric's `track2.py` is the
serving slot; this foundry is the factory that fills it. Enabling Track 2 to
*serve* a foundry student is the fabric's config-only step; promoting a candidate
*into* that slot is this module's human-approved step.

The foundry respects (and never modifies) the fabric's **generate-and-verify**
substrate: curation only admits outputs that pass the confidence gate as positive
targets, and eval's `generate_verify_pass_rate` measures served-output quality.

## Files

| File | Responsibility |
| --- | --- |
| `capture.py` | event stream -> PII-free, consent-stamped learning signals |
| `consent_gate.py` | consent + age-tier admissibility (deny-by-default; revocation; provenance) |
| `dataset.py` | versioned, deduped, PII-scrubbed datasets; splits; provenance + content hash |
| `curate.py` | safety + verify + balance filtering |
| `eval.py` | held-out + platform-meaningful scorecard; head-to-head vs incumbent |
| `finetune.py` | distillation runner; injected GPU backend; no-compute plan by default |
| `registry.py` | candidate -> scorecard -> permission-laddered PROMOTE (never auto) |
| `loop.py` | the closed continuous-learning loop (idempotent, replayable) |
| `events.py` | emit dataset-built / candidate-evaluated / promotion-requested / promoted |

## "Press go when compute is attached"

With **no** training backend configured, `finetune.run(...)` returns a
`NoComputePlan`: the distillation recipe, the dataset reference + content hash,
and the **expected** artifacts — but no model. The rest of the loop still runs:
signals are captured, gated, curated, the dataset is built and stamped, the
candidate is registered, and (given a candidate predictor) it is evaluated and a
permission-laddered promotion request is surfaced for a human.

To attach compute, set the named secrets **and** inject a `TrainingBackend`
implementation. When both are present, `finetune.run(...)` hands the raw key to
the backend seam (the key is never returned in any result object and never
logged) and returns a `TrainedCandidate`.

## Environment variable names (ENV-ONLY, never hardcoded)

Secret-name convention `clss.<app>.<env>.<purpose>`, mapped to OS env keys by
uppercasing and replacing `.`/`-` with `_` (prefix `CLSS_MODELFOUNDRY_DEV_`):

| Secret name | OS env var | Purpose |
| --- | --- | --- |
| `clss.modelfoundry.dev.training_endpoint` | `CLSS_MODELFOUNDRY_DEV_TRAINING_ENDPOINT` | GPU training backend endpoint (the compute seam) |
| `clss.modelfoundry.dev.training_key` | `CLSS_MODELFOUNDRY_DEV_TRAINING_KEY` | training backend key (read by name; never returned/logged) |

A field that is unset resolves to `None`; a partial configuration (one without
the other) is treated as unset, so the runner degrades to a no-compute plan
rather than attempting an unauthenticated call.

## Invariants enforced here

- **1 / 2** — behavioural data carries ONLY the opaque `canonical_uuid`; PII
  never enters a signal or a dataset (capture refuses it; the dataset scrub
  aborts on any leak).
- **6** — consent + age-tier gate admissibility; minors are strictly limited (a
  child is never admissible; a teen requires guardian consent); revocation
  removes a learner's contributed signals; provenance is transparent;
  deny-by-default.
- **7** — generate-and-verify + safety filtering before any example enters a
  dataset; only verify-passing outputs become positive targets.
- **8** — promoting a model to serve learners requires explicit human approval;
  it never auto-promotes; who/when is recorded immutably.
- **11** — Track 1 (external) and Track 2 (proprietary / edge) stay separate; the
  foundry only ever produces Track 2 students.

## Self-verify

```
cd spine/model-foundry
../../.venv/bin/python -m pytest -q
```

Import-safe, offline, no network, no provider call, no training.
```
