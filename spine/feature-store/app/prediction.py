"""The prediction layer (spine A3 / B11 prediction).

Forecasts from features — trajectory, exam-readiness, and risk — built ONLY from
the point-in-time feature vector. Three guarantees, each a law:

  - REPRODUCIBLE: a prediction is a pure, deterministic function of the feature
    vector. Same vector -> same prediction. No randomness, no clock, no network.
  - LINEAGE ON EVERY PREDICTION: each ``Prediction`` carries the exact features
    (name -> value) and the source ``evidence_event_ids`` that produced it, plus
    the model version and the registry signature — it can always be explained and
    reproduced (Principle 2: evidence, confidence, why-am-I-seeing-this).
  - CONFIDENCE GATE: every forecast carries a calibrated confidence and a
    plain-language band; a thin-evidence forecast is explicitly LOW confidence and
    never presented as settled (a judgment is never confirmed from one score).

These are deterministic forecasts, NOT consequential actions. Acting on a
prediction (notify, intervene, escalate) sits behind the A5 permission ladder and
human approval — never here. This module only RECOMMENDS a read of the evidence.

INVARIANT 11: a future model-assisted cross-check routes through the gateway's
Track 1 / Track 2 slots (named in config, separate, absent here). The
deterministic forecasts stand alone with no provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from .features import FeatureVector, compute_feature_vector
from .intelligence_interop import (
    EventEnvelope,
    MasteryWeights,
)

# The prediction-model version. Bump when any forecast formula changes, so a
# stored prediction names the exact model that produced it (reproducibility).
PREDICTION_MODEL_VERSION = "fs.prediction.v1"

PredictionKind = Literal["trajectory", "exam_readiness", "risk"]

TrajectoryLabel = Literal["accelerating", "improving", "steady", "stalling", "declining"]
ReadinessLabel = Literal["ready", "nearly-ready", "developing", "not-ready", "no-evidence"]
RiskLabel = Literal["low", "moderate", "elevated", "high"]
ConfidenceBand = Literal["low", "medium", "high"]

# Confidence rests on sample size first: a forecast on too little evidence is
# provisional no matter how clean the pattern (the core "never from one score").
_MIN_OBS_FOR_MEDIUM = 3
_MIN_OBS_FOR_HIGH = 6


@dataclass(frozen=True)
class Prediction:
    """A reproducible forecast carrying the features + confidence that produced it."""

    kind: PredictionKind
    subject: UUID
    topic_id: UUID
    asof: datetime
    # The headline forecast.
    label: str
    score: float  # in [0,1], the kind-specific magnitude (e.g. readiness level)
    # Confidence + its plain-language band (explainable intelligence).
    confidence: float
    confidence_band: ConfidenceBand
    # The plain-language "what this means", never a raw number to a learner.
    plain_language: str
    # Lineage: the EXACT features and source events that produced the forecast.
    features_used: dict[str, float]
    evidence_event_ids: list[UUID]
    observation_count: int
    # Versioning: the model + registry signature, for exact reproduction.
    model_version: str
    registry_signature: str
    # Why this surfaced — the human-readable rationale.
    rationale: str
    contributing_features: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Confidence — sample size first, then signal cleanliness.
# ---------------------------------------------------------------------------
def _confidence(n_obs: int, *, volatility: float, indep_count: float) -> tuple[float, ConfidenceBand]:
    """Calibrated confidence in [0,1] + band. Grows with observations and
    independent demonstrations, shrinks with volatility. Thin evidence is LOW."""
    if n_obs <= 0:
        return 0.0, "low"
    # Sample-size term: 1->~0.5, asymptotic to 1.
    size = 1.0 - 0.5 ** n_obs
    # Independent demonstrations harden the read (capped contribution).
    indep_term = min(indep_count, 3.0) / 3.0
    # Volatility erodes confidence.
    stability = 1.0 - max(0.0, min(1.0, volatility))
    conf = max(0.0, min(1.0, 0.5 * size + 0.25 * indep_term + 0.25 * stability))

    if n_obs >= _MIN_OBS_FOR_HIGH and conf >= 0.7:
        band: ConfidenceBand = "high"
    elif n_obs >= _MIN_OBS_FOR_MEDIUM and conf >= 0.5:
        band = "medium"
    else:
        band = "low"
    return conf, band


def _band_phrase(band: ConfidenceBand) -> str:
    return {
        "low": "early signal, treat as provisional",
        "medium": "a reasonable read, worth a second look",
        "high": "a well-evidenced read",
    }[band]


# ---------------------------------------------------------------------------
# Trajectory.
# ---------------------------------------------------------------------------
def _trajectory_from_vector(v: FeatureVector) -> Prediction:
    trend = v.get("success_trend")
    recent = v.get("recent_success_rate")
    overall = v.get("overall_success_rate")
    volatility = v.get("volatility")
    momentum = recent - overall  # short-horizon vs baseline

    # Combined direction score in [-1,1].
    direction = max(-1.0, min(1.0, 0.6 * trend + 0.4 * momentum))

    if direction >= 0.5:
        label: TrajectoryLabel = "accelerating"
    elif direction >= 0.15:
        label = "improving"
    elif direction > -0.15:
        label = "steady"
    elif direction > -0.5:
        label = "stalling"
    else:
        label = "declining"

    score = (direction + 1.0) / 2.0  # map [-1,1] -> [0,1]
    conf, cband = _confidence(
        v.observation_count, volatility=volatility, indep_count=v.get("independent_attempt_count")
    )
    plain = {
        "accelerating": "progress is speeding up",
        "improving": "moving in the right direction",
        "steady": "holding steady",
        "stalling": "progress has slowed — worth a check-in",
        "declining": "slipping back — review is needed",
    }[label]
    return Prediction(
        kind="trajectory",
        subject=v.subject,
        topic_id=v.topic_id,
        asof=v.asof,
        label=label,
        score=score,
        confidence=conf,
        confidence_band=cband,
        plain_language=f"{plain} ({_band_phrase(cband)})",
        features_used=v.as_dict(),
        evidence_event_ids=list(v.evidence_event_ids),
        observation_count=v.observation_count,
        model_version=PREDICTION_MODEL_VERSION,
        registry_signature=v.registry_signature,
        rationale=(
            f"Trend {trend:+.2f} and momentum {momentum:+.2f} (recent vs baseline) "
            f"combine to direction {direction:+.2f}."
        ),
        contributing_features=["success_trend", "recent_success_rate", "overall_success_rate"],
    )


# ---------------------------------------------------------------------------
# Exam-readiness.
# ---------------------------------------------------------------------------
def _exam_readiness_from_vector(v: FeatureVector) -> Prediction:
    if v.observation_count == 0:
        return Prediction(
            kind="exam_readiness",
            subject=v.subject,
            topic_id=v.topic_id,
            asof=v.asof,
            label="no-evidence",
            score=0.0,
            confidence=0.0,
            confidence_band="low",
            plain_language="no evidence yet to judge readiness",
            features_used=v.as_dict(),
            evidence_event_ids=[],
            observation_count=0,
            model_version=PREDICTION_MODEL_VERSION,
            registry_signature=v.registry_signature,
            rationale="No observations on this topic at this point in time.",
            contributing_features=[],
        )

    indep = v.get("independent_success_rate")
    difficulty = v.get("mean_difficulty_succeeded")
    recency = v.get("recency_dimension")
    composite = v.get("mastery_composite")

    # Readiness leans on INDEPENDENT capability on non-trivial items that is still
    # fresh — exactly what an exam demands. A blend, capped by independence.
    raw = 0.45 * indep + 0.25 * composite + 0.15 * difficulty + 0.15 * recency
    # Independence is the hard cap: heavily-supported success is not exam-ready.
    score = max(0.0, min(1.0, raw * (0.4 + 0.6 * indep)))

    if score >= 0.7:
        label: ReadinessLabel = "ready"
    elif score >= 0.5:
        label = "nearly-ready"
    elif score >= 0.3:
        label = "developing"
    else:
        label = "not-ready"

    conf, cband = _confidence(
        v.observation_count, volatility=v.get("volatility"), indep_count=v.get("independent_attempt_count")
    )
    plain = {
        "ready": "ready to be assessed independently",
        "nearly-ready": "close — a little more independent practice",
        "developing": "building, not yet ready to be assessed alone",
        "not-ready": "not ready yet — needs more independent work",
    }[label]
    return Prediction(
        kind="exam_readiness",
        subject=v.subject,
        topic_id=v.topic_id,
        asof=v.asof,
        label=label,
        score=score,
        confidence=conf,
        confidence_band=cband,
        plain_language=f"{plain} ({_band_phrase(cband)})",
        features_used=v.as_dict(),
        evidence_event_ids=list(v.evidence_event_ids),
        observation_count=v.observation_count,
        model_version=PREDICTION_MODEL_VERSION,
        registry_signature=v.registry_signature,
        rationale=(
            f"Independent success {indep:.2f}, difficulty {difficulty:.2f}, "
            f"recency {recency:.2f}, composite {composite:.2f} -> readiness {score:.2f}."
        ),
        contributing_features=[
            "independent_success_rate",
            "mastery_composite",
            "mean_difficulty_succeeded",
            "recency_dimension",
        ],
    )


# ---------------------------------------------------------------------------
# Risk.
# ---------------------------------------------------------------------------
def _risk_from_vector(v: FeatureVector) -> Prediction:
    if v.observation_count == 0:
        return Prediction(
            kind="risk",
            subject=v.subject,
            topic_id=v.topic_id,
            asof=v.asof,
            label="low",
            score=0.0,
            confidence=0.0,
            confidence_band="low",
            plain_language="no evidence yet to assess risk",
            features_used=v.as_dict(),
            evidence_event_ids=[],
            observation_count=0,
            model_version=PREDICTION_MODEL_VERSION,
            registry_signature=v.registry_signature,
            rationale="No observations on this topic at this point in time.",
            contributing_features=[],
        )

    overall = v.get("overall_success_rate")
    trend = v.get("success_trend")
    volatility = v.get("volatility")
    recency = v.get("recency_dimension")
    indep = v.get("independent_success_rate")

    # Risk rises with weak performance, a declining trend, high volatility, stale
    # evidence, and weak independent transfer. A bounded weighted sum.
    weak = 1.0 - overall
    declining = max(0.0, -trend)
    stale = 1.0 - recency
    not_independent = 1.0 - indep
    raw = (
        0.30 * weak
        + 0.25 * declining
        + 0.15 * volatility
        + 0.15 * stale
        + 0.15 * not_independent
    )
    score = max(0.0, min(1.0, raw))

    if score >= 0.65:
        label: RiskLabel = "high"
    elif score >= 0.45:
        label = "elevated"
    elif score >= 0.25:
        label = "moderate"
    else:
        label = "low"

    conf, cband = _confidence(
        v.observation_count, volatility=volatility, indep_count=v.get("independent_attempt_count")
    )
    plain = {
        "high": "falling behind — needs attention",
        "elevated": "some warning signs — worth reviewing",
        "moderate": "a few signals to keep an eye on",
        "low": "no concerning signals",
    }[label]
    return Prediction(
        kind="risk",
        subject=v.subject,
        topic_id=v.topic_id,
        asof=v.asof,
        label=label,
        score=score,
        confidence=conf,
        confidence_band=cband,
        plain_language=f"{plain} ({_band_phrase(cband)})",
        features_used=v.as_dict(),
        evidence_event_ids=list(v.evidence_event_ids),
        observation_count=v.observation_count,
        model_version=PREDICTION_MODEL_VERSION,
        registry_signature=v.registry_signature,
        rationale=(
            f"Weak {weak:.2f}, declining {declining:.2f}, volatility {volatility:.2f}, "
            f"stale {stale:.2f}, non-independence {not_independent:.2f} -> risk {score:.2f}. "
            "Acting on this requires human approval (permission ladder)."
        ),
        contributing_features=[
            "overall_success_rate",
            "success_trend",
            "volatility",
            "recency_dimension",
            "independent_success_rate",
        ],
    )


# ---------------------------------------------------------------------------
# Public entry points — predict from a vector, or from events (point-in-time).
# ---------------------------------------------------------------------------
def predict_from_vector(vector: FeatureVector, *, kind: PredictionKind) -> Prediction:
    """Forecast of ``kind`` from an already-computed point-in-time vector. Pure
    and deterministic: same vector + kind -> identical prediction."""
    if kind == "trajectory":
        return _trajectory_from_vector(vector)
    if kind == "exam_readiness":
        return _exam_readiness_from_vector(vector)
    if kind == "risk":
        return _risk_from_vector(vector)
    raise ValueError(f"Unknown prediction kind: {kind!r}")


def predict_all_from_vector(vector: FeatureVector) -> dict[PredictionKind, Prediction]:
    """All three forecasts from one vector, sharing the same feature lineage."""
    return {
        "trajectory": _trajectory_from_vector(vector),
        "exam_readiness": _exam_readiness_from_vector(vector),
        "risk": _risk_from_vector(vector),
    }


def predict(
    events: list[EventEnvelope],
    *,
    kind: PredictionKind,
    subject: UUID,
    topic_id: UUID,
    asof: datetime | None = None,
    weights: MasteryWeights | None = None,
) -> Prediction:
    """Forecast of ``kind`` for one (learner, topic) point-in-time, from events.

    Builds the point-in-time feature vector (no future leakage) then forecasts
    from it. Reproducible: identical events + ``asof`` -> identical prediction
    carrying the features + confidence + lineage that produced it.
    """
    vector = compute_feature_vector(
        events, subject=subject, topic_id=topic_id, asof=asof, weights=weights
    )
    return predict_from_vector(vector, kind=kind)


def predict_all(
    events: list[EventEnvelope],
    *,
    subject: UUID,
    topic_id: UUID,
    asof: datetime | None = None,
    weights: MasteryWeights | None = None,
) -> dict[PredictionKind, Prediction]:
    """All three forecasts for one (learner, topic), sharing one vector."""
    vector = compute_feature_vector(
        events, subject=subject, topic_id=topic_id, asof=asof, weights=weights
    )
    return predict_all_from_vector(vector)
