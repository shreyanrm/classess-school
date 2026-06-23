"""The governed semantic layer — one metric, defined ONCE, computed the same
everywhere.

This is the keystone of B11. Every dashboard, every quadrant, every forecast, and
the ask-anything interface resolve their numbers through THIS registry. A metric
is defined exactly once here, with:

  - a stable ``key`` (the canonical name surfaced nowhere raw to a learner),
  - the plain-language ``label`` and ``definition`` (what it means, in words),
  - the single ``compute`` function (the one true definition),
  - the ``grain`` it is valid at (learner / cohort / topic),
  - the ``unit`` and whether it is ``learner_safe`` (may a learner see a raw
    number, or must it be banded into plain language — principle: never a raw
    number or formula to a learner/parent).

Two screens asking for "mastery" get the SAME number from the SAME function. A
metric cannot be redefined ad hoc in a view: views call ``resolve``/``compute``,
they never reimplement the maths. Registering two definitions under one key
raises — the contract that makes the layer governed rather than a free-for-all.

CONFIDENTIALITY: labels and definitions are generic and plain-language. No real
names, no codenames, no board lock-in, no emoji, no exclamation marks. No raw
formula is ever surfaced to a learner/parent; ``learner_safe`` gates that.

Pure and deterministic: same inputs, same metric value — reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class MetricGrain(str, Enum):
    """The level a metric is valid at. A metric is defined for exactly one grain
    so a cohort number and a learner number are never silently conflated."""

    LEARNER = "learner"
    COHORT = "cohort"
    TOPIC = "topic"


@dataclass(frozen=True)
class MetricContext:
    """The inputs a metric is computed over.

    ``profiles`` is the list of per-learner projections (LearnerProfile objects
    or equivalently-shaped duck types) in scope. ``topic_id`` / ``subject`` scope
    a topic- or learner-grain metric. ``extra`` carries any view-specific,
    PII-free context (e.g. a coverage map). Everything here is keyed by opaque
    refs only — INVARIANT 1/2: no PII ever enters a metric computation.
    """

    profiles: list[Any]
    topic_id: Any | None = None
    subject: Any | None = None
    extra: dict[str, Any] | None = None

    def topic_projections(self) -> list[Any]:
        """The per-learner projection for ``topic_id`` across all in-scope
        profiles, skipping learners with no evidence on it."""
        if self.topic_id is None:
            return []
        out: list[Any] = []
        for prof in self.profiles:
            proj = prof.topic(self.topic_id)
            if proj is not None:
                out.append(proj)
        return out


MetricFn = Callable[[MetricContext], float]


@dataclass(frozen=True)
class MetricValue:
    """A computed metric, resolved through the registry.

    Carries the canonical key, the plain-language label, the raw value, and — for
    surfaces — the plain-language banding. ``shown_to_learner`` is the only thing
    a learner/parent surface should render when ``learner_safe`` is False: the
    raw number stays internal.
    """

    key: str
    label: str
    value: float
    unit: str
    grain: MetricGrain
    plain_language: str
    learner_safe: bool
    definition: str

    def shown_to_learner(self) -> str:
        """The single thing a learner/parent surface renders. Never the raw
        number or the formula when the metric is not learner-safe."""
        return self.plain_language


@dataclass(frozen=True)
class MetricDefinition:
    """A metric defined ONCE. The compute function is the single source of truth."""

    key: str
    label: str
    definition: str
    grain: MetricGrain
    unit: str
    compute: MetricFn
    learner_safe: bool = False
    #: Maps a raw value to plain language (never a raw number to a learner).
    band: Callable[[float], str] | None = None

    def plain_language_for(self, value: float) -> str:
        if self.band is not None:
            return self.band(value)
        # Fall back to a neutral, number-free phrasing.
        return self.label


class MetricRedefinitionError(ValueError):
    """Raised when a key is registered twice with a different definition — the
    governance guarantee that a metric is defined exactly once."""


class SemanticLayer:
    """The metric registry. One definition per key; views resolve through it.

    The governance rule lives here: ``register`` refuses to overwrite a key with
    a different definition, so no view can fork a metric's meaning. Re-registering
    the IDENTICAL definition object is a harmless no-op (idempotent module load).
    """

    def __init__(self) -> None:
        self._defs: dict[str, MetricDefinition] = {}

    def register(self, definition: MetricDefinition) -> MetricDefinition:
        existing = self._defs.get(definition.key)
        if existing is not None and existing is not definition:
            raise MetricRedefinitionError(
                f"Metric '{definition.key}' is already defined. A metric is "
                "defined exactly once and computed the same everywhere; redefining "
                "it in a view is forbidden. Resolve through the existing definition."
            )
        self._defs[definition.key] = definition
        return definition

    def define(self, **kwargs: Any) -> MetricDefinition:
        """Convenience: build and register in one call."""
        return self.register(MetricDefinition(**kwargs))

    def get(self, key: str) -> MetricDefinition:
        try:
            return self._defs[key]
        except KeyError as exc:
            raise KeyError(
                f"Unknown metric '{key}'. Define it once in the semantic layer; "
                "views never compute an undefined metric inline."
            ) from exc

    def keys(self) -> list[str]:
        return sorted(self._defs)

    def compute(self, key: str, context: MetricContext) -> MetricValue:
        """Resolve and compute a metric. The ONE place a number is produced for a
        given key — every view goes through here."""
        definition = self.get(key)
        raw = definition.compute(context)
        # Clamp defensively into the unit's nominal range; ratios are [0,1].
        if definition.unit == "ratio":
            raw = max(0.0, min(1.0, raw))
        return MetricValue(
            key=definition.key,
            label=definition.label,
            value=raw,
            unit=definition.unit,
            grain=definition.grain,
            plain_language=definition.plain_language_for(raw),
            learner_safe=definition.learner_safe,
            definition=definition.definition,
        )


# ---------------------------------------------------------------------------
# Plain-language banders (never a raw number to a learner/parent)
# ---------------------------------------------------------------------------
def _mastery_band_words(v: float) -> str:
    if v >= 0.55:
        return "on track and independent"
    if v >= 0.32:
        return "secure with a little support"
    if v >= 0.16:
        return "developing"
    if v > 0:
        return "just getting started"
    return "not started yet"


def _coverage_band_words(v: float) -> str:
    if v >= 0.9:
        return "nearly all planned material delivered"
    if v >= 0.6:
        return "most planned material delivered"
    if v >= 0.3:
        return "some planned material delivered"
    return "little planned material delivered so far"


def _effort_band_words(v: float) -> str:
    if v >= 0.66:
        return "consistent effort"
    if v >= 0.33:
        return "some effort"
    return "low effort so far"


def _share_band_words(v: float) -> str:
    if v >= 0.5:
        return "many learners affected"
    if v >= 0.2:
        return "several learners affected"
    if v > 0:
        return "a few learners affected"
    return "no learners affected"


# ---------------------------------------------------------------------------
# The ONE definition of each metric. Computed here, once.
# ---------------------------------------------------------------------------
def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _metric_topic_mastery(ctx: MetricContext) -> float:
    """Average composite mastery on one topic across in-scope learners.

    The composite is the spine mastery model's collapsed reading (for RANKING
    only — never shown raw to a learner). This is the single definition of
    'cohort mastery on a topic'."""
    projs = ctx.topic_projections()
    return _mean([p.mastery.reading.composite for p in projs])


def _metric_learner_topic_mastery(ctx: MetricContext) -> float:
    """One learner's composite mastery on one topic."""
    if ctx.subject is None or ctx.topic_id is None:
        return 0.0
    for prof in ctx.profiles:
        if prof.subject == ctx.subject:
            proj = prof.topic(ctx.topic_id)
            return proj.mastery.reading.composite if proj is not None else 0.0
    return 0.0


def _metric_independence(ctx: MetricContext) -> float:
    """Average INDEPENDENCE dimension on one topic — the keystone read: can the
    cohort do this WITHOUT help. Defined once so 'independence' means the same
    thing on every screen."""
    projs = ctx.topic_projections()
    return _mean([p.mastery.reading.dimensions.independence for p in projs])


def _metric_confirmed_gap_share(ctx: MetricContext) -> float:
    """Share of in-scope learners with at least one CONFIRMED gap on the topic.

    A gap is never confirmed from a single score (the spine guarantees that); this
    metric counts only confirmed gaps so the dashboards never alarm on a lone
    bad result."""
    projs = ctx.topic_projections()
    if not projs:
        return 0.0
    affected = sum(1 for p in projs if p.confirmed_gaps)
    return affected / len(projs)


def _metric_coverage(ctx: MetricContext) -> float:
    """Delivered / planned for the topic — the curriculum coverage ratio.

    Reads a PII-free coverage map from ``extra['coverage']``: a dict of
    ``{topic_id: (delivered, planned)}``. Absent or planned==0 -> 0.0. This is the
    single definition of 'coverage' shared by prediction and target analytics."""
    extra = ctx.extra or {}
    coverage = extra.get("coverage") or {}
    pair = coverage.get(ctx.topic_id)
    if not pair:
        return 0.0
    delivered, planned = pair
    if planned <= 0:
        return 0.0
    return delivered / planned


def _metric_effort(ctx: MetricContext) -> float:
    """Average effort signal on the topic across learners.

    Effort is an OBSERVED, PII-free engagement proxy supplied per learner in
    ``extra['effort'][subject]`` in [0,1] (attempts made, time-on-task, retrieval
    practice done — momentum toward INDEPENDENCE, never raw engagement for its own
    sake, per the central-tension rule). Absent -> derived from observation count
    so the quadrant still places a learner deterministically."""
    extra = ctx.extra or {}
    effort_map = extra.get("effort") or {}
    values: list[float] = []
    for prof in ctx.profiles:
        if ctx.topic_id is not None and prof.topic(ctx.topic_id) is None:
            continue
        supplied = effort_map.get(prof.subject)
        if supplied is not None:
            values.append(max(0.0, min(1.0, float(supplied))))
        else:
            proj = prof.topic(ctx.topic_id) if ctx.topic_id is not None else None
            n = proj.mastery.observation_count if proj is not None else 0
            # Saturating proxy: more demonstrated work -> more observed effort.
            values.append(1.0 - 0.6 ** n if n > 0 else 0.0)
    return _mean(values)


def build_default_semantic_layer() -> SemanticLayer:
    """The built-in registry. Every B11 view uses THIS, so a metric is computed
    the same everywhere. A gateway-backed semantic-layer service would expose the
    same keys/definitions; the deterministic registry is the supported path while
    no provider is configured."""
    layer = SemanticLayer()
    layer.define(
        key="topic_mastery",
        label="Mastery on this topic",
        definition=(
            "The cohort's average demonstrated mastery on a topic, from the spine "
            "six-dimension mastery model. Banded into plain language for learners; "
            "the raw composite is internal only."
        ),
        grain=MetricGrain.TOPIC,
        unit="ratio",
        compute=_metric_topic_mastery,
        learner_safe=False,
        band=_mastery_band_words,
    )
    layer.define(
        key="learner_topic_mastery",
        label="Your mastery on this topic",
        definition=(
            "One learner's demonstrated mastery on a topic, from the spine "
            "mastery model. Shown to a learner only as plain language."
        ),
        grain=MetricGrain.LEARNER,
        unit="ratio",
        compute=_metric_learner_topic_mastery,
        learner_safe=False,
        band=_mastery_band_words,
    )
    layer.define(
        key="independence",
        label="Can do this without help",
        definition=(
            "The cohort's average Independence dimension on a topic — whether the "
            "work is produced independently rather than only with support. The "
            "keystone read; defined once."
        ),
        grain=MetricGrain.TOPIC,
        unit="ratio",
        compute=_metric_independence,
        learner_safe=False,
        band=_mastery_band_words,
    )
    layer.define(
        key="confirmed_gap_share",
        label="Learners with a confirmed gap",
        definition=(
            "Share of in-scope learners with at least one CONFIRMED gap on the "
            "topic. Confirmed only — never alarms on a single bad score."
        ),
        grain=MetricGrain.TOPIC,
        unit="ratio",
        compute=_metric_confirmed_gap_share,
        learner_safe=False,
        band=_share_band_words,
    )
    layer.define(
        key="coverage",
        label="Material delivered",
        definition=(
            "Delivered divided by planned for the topic — how much of the planned "
            "curriculum has actually been taught. Shared by prediction and target "
            "analytics so 'coverage' means one thing."
        ),
        grain=MetricGrain.TOPIC,
        unit="ratio",
        compute=_metric_coverage,
        learner_safe=True,
        band=_coverage_band_words,
    )
    layer.define(
        key="effort",
        label="Effort",
        definition=(
            "An observed, PII-free effort proxy on the topic (work attempted, "
            "retrieval practice done) — momentum toward independence, not raw "
            "engagement. The x-axis of the study quadrant."
        ),
        grain=MetricGrain.TOPIC,
        unit="ratio",
        compute=_metric_effort,
        learner_safe=True,
        band=_effort_band_words,
    )
    return layer
