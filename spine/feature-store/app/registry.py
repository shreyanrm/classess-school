"""The feature registry — one definition, computed the same everywhere.

Principle 2/B11: "one metric, defined once, computed the same everywhere." A
feature is NOT an ad-hoc number sprinkled across surfaces; it is a single named,
VERSIONED definition with a pure compute function. Every surface (dashboards,
study quadrant, prediction) that needs "independent success rate" reads THIS
definition — there is exactly one.

Each ``FeatureDefinition`` carries:

  - ``name``: the stable, opaque feature key.
  - ``version``: bumped when the computation changes, so a stored feature value
    always names the definition version that produced it (lineage + reproducibility).
  - ``dtype`` / ``unit``: the value's type and unit, for the semantic layer.
  - ``description`` + ``rationale``: explainable intelligence — why this exists.
  - ``compute``: a PURE function ``(FeatureInputs) -> float`` over a
    POINT-IN-TIME evidence trail. No future leakage: the inputs are already
    filtered to ``asof`` by ``features.py`` before any compute runs.

The definitions are deterministic and have NO external dependencies. They read
the intelligence engine's evidence/mastery output, never reauthoring it.

INVARIANT 1: every input is keyed by the opaque ``canonical_uuid`` and opaque
topic ids only — no PII ever enters a feature.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal

from .intelligence_interop import (
    EvidenceItem,
    MasteryResult,
    assistance_rank,
)

# A registry-wide version stamp. Bump when the SET of features or the shared
# computation conventions change in a way that affects stored values. Each
# definition also carries its own version; the snapshot records both.
REGISTRY_VERSION = "fs.registry.v1"

FeatureDType = Literal["ratio", "count", "seconds", "score", "band"]


@dataclass(frozen=True)
class FeatureInputs:
    """The POINT-IN-TIME inputs a feature is computed from.

    ``items`` is the evidence trail for ONE (learner, topic) already filtered to
    ``asof`` (no observation after ``asof`` is present — no future leakage) and
    sorted chronologically by the engine. ``mastery`` is the engine's mastery
    reading computed over exactly that same trail at exactly ``asof``.

    A feature compute sees ONLY this struct — it cannot reach outside the
    point-in-time window, which is what guarantees point-in-time correctness.
    """

    subject: object  # opaque canonical_uuid (UUID) — typed loosely to avoid import churn
    topic_id: object  # opaque ontology topic id (UUID)
    asof: datetime
    items: list[EvidenceItem]
    mastery: MasteryResult


# Compute signature: pure, deterministic, point-in-time.
ComputeFn = Callable[[FeatureInputs], float]


@dataclass(frozen=True)
class FeatureDefinition:
    """One feature, defined once. Versioned and self-describing."""

    name: str
    version: str
    dtype: FeatureDType
    unit: str
    description: str
    rationale: str
    compute: ComputeFn

    @property
    def key(self) -> str:
        """The stable, versioned identifier stamped onto every computed value."""
        return f"{self.name}@{self.version}"


# ---------------------------------------------------------------------------
# Helpers shared by definitions (kept tiny + pure). The recency-weighting and
# independence/assistance semantics belong to the engine; here we only COUNT and
# AGGREGATE the already-normalized evidence items.
# ---------------------------------------------------------------------------
def _safe_div(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def _weighted_mean_score(items: list[EvidenceItem], *, asof: datetime) -> float:
    num = sum(it.score * it.weight(asof=asof) for it in items)
    den = sum(it.weight(asof=asof) for it in items)
    return _safe_div(num, den)


# ---------------------------------------------------------------------------
# The feature definitions.
# ---------------------------------------------------------------------------
def _f_observation_count(x: FeatureInputs) -> float:
    return float(len(x.items))


def _f_independent_attempt_count(x: FeatureInputs) -> float:
    return float(sum(1 for it in x.items if it.independent))


def _f_independent_success_rate(x: FeatureInputs) -> float:
    """Recency-weighted share of SUCCESS that was produced independently — the
    keystone read. Mirrors the spirit of the engine's Independence dimension but
    exposed as a standalone, point-in-time feature for forecasting."""
    indep = [it for it in x.items if it.independent]
    return _weighted_mean_score(indep, asof=x.asof)


def _f_overall_success_rate(x: FeatureInputs) -> float:
    return _weighted_mean_score(x.items, asof=x.asof)


def _f_recent_success_rate(x: FeatureInputs) -> float:
    """Success rate over the most recent third of the trail (min 3 items). A
    short-horizon read used to judge MOMENTUM against the longer baseline."""
    n = len(x.items)
    if n == 0:
        return 0.0
    window = max(3, n // 3)
    recent = x.items[-window:]
    return _weighted_mean_score(recent, asof=x.asof)


def _f_success_trend(x: FeatureInputs) -> float:
    """Slope of success over the chronological trail, normalized to [-1, 1].

    Positive => improving (the basis of an upward trajectory); negative =>
    declining (a risk signal). A simple least-squares slope on the score
    sequence, scaled so a full 0->1 climb across the trail reads ~+1.
    """
    scores = [it.score for it in x.items]
    n = len(scores)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(scores)
    denom = sum((xi - mean_x) ** 2 for xi in xs)
    if denom == 0:
        return 0.0
    slope = sum((xs[i] - mean_x) * (scores[i] - mean_y) for i in range(n)) / denom
    # slope is per-step; scale by (n-1) to express the total climb across trail.
    total_change = slope * (n - 1)
    return max(-1.0, min(1.0, total_change))


def _f_volatility(x: FeatureInputs) -> float:
    """Population standard deviation of the score sequence in [0,1] — erratic
    performance reads high. The inverse signal to the engine's Consistency."""
    scores = [it.score for it in x.items]
    if len(scores) < 2:
        return 0.0
    return max(0.0, min(1.0, statistics.pstdev(scores)))


def _f_mean_difficulty_succeeded(x: FeatureInputs) -> float:
    """Average difficulty of items SUCCEEDED on (score>0), recency-weighted.
    Distinguishes hard-won mastery from easy-only success for trajectory."""
    succ = [it for it in x.items if it.score > 0]
    num = sum(it.difficulty * it.weight(asof=x.asof) for it in succ)
    den = sum(it.weight(asof=x.asof) for it in succ)
    return _safe_div(num, den)


def _f_days_since_last_evidence(x: FeatureInputs) -> float:
    """Staleness: days from the freshest observation to ``asof``. Drives the
    retention/risk forecast (links to the engine's recency dimension)."""
    if not x.items:
        return 0.0
    latest = max(it.occurred_at for it in x.items)
    delta = x.asof - latest
    return max(0.0, delta.total_seconds() / 86400.0)


def _f_mean_assistance_rank(x: FeatureInputs) -> float:
    """Average position on the assistance ladder (0 most-help .. 5 none),
    normalized to [0,1]. Rising over time => fading support => healthy."""
    if not x.items:
        return 0.0
    ranks = [assistance_rank(it.assistance_level) for it in x.items]
    return _safe_div(statistics.mean(ranks), 5.0)


def _f_recency_dimension(x: FeatureInputs) -> float:
    """The engine's own recency dimension, surfaced as a feature so forecasting
    and surfaces read the SAME freshness number the mastery reading used."""
    return x.mastery.reading.dimensions.recency


def _f_mastery_composite(x: FeatureInputs) -> float:
    """The engine's composite mastery (ranking-only). Carried as a feature for
    forecasting; surfaces still show the band/plain-language, never this raw
    number (the engine's INVARIANT)."""
    return x.mastery.reading.composite


_DEFINITIONS: tuple[FeatureDefinition, ...] = (
    FeatureDefinition(
        name="observation_count",
        version="v1",
        dtype="count",
        unit="observations",
        description="Number of evidence observations on the topic at asof.",
        rationale="Sample size gates confidence; a forecast on one observation is provisional.",
        compute=_f_observation_count,
    ),
    FeatureDefinition(
        name="independent_attempt_count",
        version="v1",
        dtype="count",
        unit="attempts",
        description="Number of fully-independent attempts at asof.",
        rationale="Independent demonstrations are the evidence exam-readiness rests on.",
        compute=_f_independent_attempt_count,
    ),
    FeatureDefinition(
        name="independent_success_rate",
        version="v1",
        dtype="ratio",
        unit="fraction",
        description="Recency-weighted success rate on independent attempts only.",
        rationale="The keystone read: capability that transfers without support.",
        compute=_f_independent_success_rate,
    ),
    FeatureDefinition(
        name="overall_success_rate",
        version="v1",
        dtype="ratio",
        unit="fraction",
        description="Recency-weighted success rate across all attempts.",
        rationale="Baseline performance, supported and independent combined.",
        compute=_f_overall_success_rate,
    ),
    FeatureDefinition(
        name="recent_success_rate",
        version="v1",
        dtype="ratio",
        unit="fraction",
        description="Success rate over the most recent window of the trail.",
        rationale="Short-horizon read for momentum against the longer baseline.",
        compute=_f_recent_success_rate,
    ),
    FeatureDefinition(
        name="success_trend",
        version="v1",
        dtype="ratio",
        unit="signed-fraction",
        description="Normalized slope of success across the trail, in [-1,1].",
        rationale="Direction of travel: the core trajectory signal.",
        compute=_f_success_trend,
    ),
    FeatureDefinition(
        name="volatility",
        version="v1",
        dtype="ratio",
        unit="stddev",
        description="Std-dev of the score sequence in [0,1].",
        rationale="Erratic performance lowers forecast confidence and flags risk.",
        compute=_f_volatility,
    ),
    FeatureDefinition(
        name="mean_difficulty_succeeded",
        version="v1",
        dtype="ratio",
        unit="fraction",
        description="Recency-weighted mean difficulty of succeeded items.",
        rationale="Hard-won success forecasts higher than easy-only success.",
        compute=_f_mean_difficulty_succeeded,
    ),
    FeatureDefinition(
        name="days_since_last_evidence",
        version="v1",
        dtype="seconds",
        unit="days",
        description="Days from the freshest observation to asof.",
        rationale="Staleness drives the retention-risk forecast.",
        compute=_f_days_since_last_evidence,
    ),
    FeatureDefinition(
        name="mean_assistance_rank",
        version="v1",
        dtype="ratio",
        unit="fraction",
        description="Mean assistance-ladder position normalized to [0,1].",
        rationale="Rising over time means support is fading — a healthy trajectory.",
        compute=_f_mean_assistance_rank,
    ),
    FeatureDefinition(
        name="recency_dimension",
        version="v1",
        dtype="ratio",
        unit="fraction",
        description="The engine's recency dimension at asof.",
        rationale="One freshness number, shared with the mastery reading.",
        compute=_f_recency_dimension,
    ),
    FeatureDefinition(
        name="mastery_composite",
        version="v1",
        dtype="score",
        unit="fraction",
        description="The engine's ranking-only composite mastery at asof.",
        rationale="Carried for forecasting; never shown raw to a learner.",
        compute=_f_mastery_composite,
    ),
)


# Name -> definition. One canonical lookup; duplicate names are a defect.
_REGISTRY: dict[str, FeatureDefinition] = {}
for _d in _DEFINITIONS:
    if _d.name in _REGISTRY:
        raise ValueError(f"Duplicate feature definition name: {_d.name}")
    _REGISTRY[_d.name] = _d


def all_definitions() -> list[FeatureDefinition]:
    """Every registered feature definition, in a stable order (by name)."""
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]


def feature_names() -> list[str]:
    """The stable, sorted list of feature names."""
    return sorted(_REGISTRY)


def get_definition(name: str) -> FeatureDefinition:
    """Look up one definition by name. Raises ``KeyError`` if unknown — a typo in
    a feature name must fail loudly, never silently return a different metric."""
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown feature '{name}'. Known features: {feature_names()}. "
            "Every feature is defined ONCE in the registry; add it here, do not "
            "compute it ad-hoc at a call site."
        )
    return _REGISTRY[name]


def registry_signature() -> str:
    """A deterministic signature of the registry contents — the registry version
    plus every definition key. Stamped onto snapshots so a stored feature set can
    be matched to the exact definitions that produced it (reproducibility)."""
    keys = ",".join(d.key for d in all_definitions())
    return f"{REGISTRY_VERSION}|{keys}"
