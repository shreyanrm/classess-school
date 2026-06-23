# Classess Feature Store and Prediction Layer (spine A3, Ring 2)

The derived feature store and the prediction layer that sits on top of it. It
computes derived, versioned features per learner and topic, and forecasts
trajectory, exam-readiness, and risk from those features. Like every derived
store in the spine, it is a **projection built by replaying the immutable event
log** — it never authors features or predictions directly.

It **consumes** the intelligence engine (spine A3, the evidence to mastery to
gap engine in `spine/intelligence`) through a single audited seam
(`app/intelligence_interop.py`). It does not reimplement mastery, gaps, or
evidence weighting; it reads the engine's point-in-time output and turns it into
features and forecasts. The engine source is never modified.

Pure and deterministic, no external calls. The same events in always yield the
same features and the same predictions out. That is what makes rebuilds
reproducible, predictions auditable, and "understanding of every past learner
improves as the models improve" true in practice: re-run the current models over
the old events and every learner is re-understood, with no new data.

## What it owns

- `registry.py` — the feature definitions. One definition, computed the same
  everywhere (Principle 2 and B11: one metric, defined once, computed the same
  everywhere). Each definition is named, **versioned**, self-describing
  (description, rationale, dtype, unit), and has a pure compute function over a
  point-in-time evidence window. Every computed value is stamped with the
  definition key (`name@version`) so a stored feature always names the exact
  definition that produced it. A typo in a feature name fails loudly; it never
  silently returns a different metric.
- `features.py` — the feature store. For one (learner, topic) as of a point in
  time it filters events to that instant, computes the engine's mastery over
  exactly that window, then runs every registry definition to build the
  versioned feature vector with full lineage (the source event ids). **Point-in-
  time correct: no future leakage, ever.**
- `prediction.py` — the prediction layer. Trajectory, exam-readiness, and risk
  forecasts built only from a point-in-time feature vector. **Reproducible** (a
  pure function of the vector), and **every prediction carries the features and
  the confidence that produced it** plus the source event ids, the model
  version, and the registry signature. A thin-evidence forecast is explicitly
  low confidence and never presented as settled.
- `backfill.py` — rebuild the feature store by replaying an event list.
  **Idempotent** (replaying the same events at the same instant yields an
  identical content signature) and point-in-time correct. Also builds a leak-
  free point-in-time series across past instants — the training set for any
  model, with no leakage by construction.

## Point-in-time correctness (the leakage guard)

A feature computed as of a past instant depends only on events that occurred at
or before that instant. The single filter `events_asof` is applied once, before
any evidence is collected, so leakage is structurally impossible for every
downstream feature and prediction. Appending a future event never mutates an
earlier point-in-time vector.

## Predictions are reads, not actions

A prediction recommends a read of the evidence. It is not a consequential
action. Acting on a forecast (notify, intervene, escalate) sits behind the
proactive workflow engine (A5) and the permission ladder, with human approval
on anything consequential — never in this module. Each risk forecast says so in
its own rationale.

## Privacy and tracks

Keyed by the opaque `canonical_uuid` and opaque ontology topic ids only. No PII
ever enters a feature or a prediction (security invariants 1 and 2). Track 1
(external model routing) and Track 2 (proprietary or edge models) stay separate
in config, both as names only; the deterministic paths work with no provider in
either track (invariant 11).

## Environment (names only, never values)

Secrets and endpoints are environment-only, read by name, never hardcoded
(invariant 4). Dotted names map to `CLSS_FEATURE_STORE_DEV_*` env vars.

- `clss.feature-store.dev.database_url` — the immutable event log to replay
  (read only; the store never writes events). Unset degrades to an in-memory
  event list, which is bit-identical to the wired path because the projection
  is pure.
- `clss.feature-store.dev.gateway_url` — the only egress. The store reaches the
  event store and ontology service through the gateway, never directly
  (invariant 3).
- `clss.feature-store.dev.feature_cache_url` — optional materialized feature
  snapshot cache. Absent means recompute from events each time (still
  deterministic).
- `clss.feature-store.dev.track1_forecast_model_key` — name only. Reserved for a
  future external-routed forecast cross-check (Track 1). No value is stored.
- `clss.feature-store.dev.track2_forecast_model_key` — name only. The separate
  Track 2 slot, present from the start, filled later with no re-architecture. No
  value is stored.

With no event source or gateway configured the store still runs over the
in-memory event list passed in, and every result names (never values) the env
vars whose absence kept it degraded.

## Tests

```
pytest
```

Import-safe and offline. No network, no DB, no provider. The suite proves: the
registry is the single source of every feature; feature rebuild is deterministic
and idempotent (including under shuffled input order); point-in-time correctness
(a past feature ignores later events; the point-in-time series is leak-free);
predictions are reproducible and carry their features, confidence, and lineage;
the confidence gate keeps thin evidence provisional; and backfill is idempotent
via a content signature.

The runtime dependency footprint (`requirements.txt`) is stdlib plus pydantic,
matching the intelligence engine it consumes; the engine is imported directly
from source, so no extra runtime dependency is introduced.
