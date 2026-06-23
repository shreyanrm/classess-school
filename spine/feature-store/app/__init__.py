"""Classess Feature Store + Prediction Layer (spine A3, Ring 2 intelligence depth).

A derived-store PROJECTION built by REPLAYING immutable events — never authored
directly. It CONSUMES the intelligence engine (spine A3 evidence -> mastery ->
gap) and turns its point-in-time output into:

  - features: derived, versioned features per learner/topic, point-in-time
    correct (no future leakage), each value stamped with its definition version.
  - registry: feature definitions — one definition, computed the same everywhere.
  - prediction: trajectory / exam-readiness / risk forecasting from features,
    reproducible, each prediction carrying the features + confidence + lineage
    that produced it.
  - backfill: rebuild features by replaying an event list — idempotent and
    point-in-time correct, the basis of "re-understand every past learner as the
    models improve" and of leak-free training-set construction.

Pure and deterministic. Holds NO credentials and makes NO external calls. With no
event source configured it degrades to an in-memory event list — the
deterministic paths are bit-identical either way (what makes rebuilds reproducible).
"""

from __future__ import annotations

from .backfill import (
    BackfillResult,
    backfill,
    backfill_point_in_time_series,
    is_idempotent,
)
from .config import FeatureStoreSettings, get_settings
from .features import (
    FeatureValue,
    FeatureVector,
    LearnerFeatureSnapshot,
    build_learner_snapshot,
    compute_feature_vector,
    compute_single_feature,
    events_asof,
)
from .prediction import (
    PREDICTION_MODEL_VERSION,
    Prediction,
    PredictionKind,
    predict,
    predict_all,
    predict_all_from_vector,
    predict_from_vector,
)
from .registry import (
    REGISTRY_VERSION,
    FeatureDefinition,
    FeatureInputs,
    all_definitions,
    feature_names,
    get_definition,
    registry_signature,
)

__all__ = [
    # config
    "FeatureStoreSettings",
    "get_settings",
    # registry
    "REGISTRY_VERSION",
    "FeatureDefinition",
    "FeatureInputs",
    "all_definitions",
    "feature_names",
    "get_definition",
    "registry_signature",
    # features
    "FeatureValue",
    "FeatureVector",
    "LearnerFeatureSnapshot",
    "build_learner_snapshot",
    "compute_feature_vector",
    "compute_single_feature",
    "events_asof",
    # prediction
    "PREDICTION_MODEL_VERSION",
    "Prediction",
    "PredictionKind",
    "predict",
    "predict_all",
    "predict_all_from_vector",
    "predict_from_vector",
    # backfill
    "BackfillResult",
    "backfill",
    "backfill_point_in_time_series",
    "is_idempotent",
]
