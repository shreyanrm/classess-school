"""The feature store: derived, versioned features per learner/topic.

A PROJECTION built by REPLAYING immutable events — never authored directly
(spine A3). For one (learner, topic) ``asof`` a point in time, it:

  1. filters the event list to events that OCCURRED at or before ``asof``
     (POINT-IN-TIME correctness — no future leakage, ever),
  2. computes the intelligence engine's mastery reading over EXACTLY that
     point-in-time evidence trail (the engine, consumed not reimplemented),
  3. runs every registry definition over that same window to produce the
     versioned feature vector, each value stamped with the definition key.

Determinism + idempotence: the same events + the same ``asof`` always produce
the same vector, because every step is pure and the trail is sorted
deterministically by the engine. Re-running the store over old events with a new
model improves understanding of every past learner — the A3 promise.

INVARIANT 1/2: keyed by the opaque ``canonical_uuid`` and opaque topic ids only.
No PII enters the feature store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .intelligence_interop import (
    EventEnvelope,
    EvidenceItem,
    MasteryResult,
    MasteryWeights,
    PrerequisiteGraph,
    collect_evidence,
    compute_mastery,
)
from .registry import (
    FeatureInputs,
    all_definitions,
    get_definition,
    registry_signature,
)


def _now_utc() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Point-in-time event windowing — the leakage guard.
# ---------------------------------------------------------------------------
def events_asof(events: list[EventEnvelope], *, asof: datetime) -> list[EventEnvelope]:
    """Return only events that OCCURRED at or before ``asof``.

    This is the single point-in-time filter. A feature computed for ``asof`` must
    never see an observation from the future; filtering here, once, before any
    evidence is collected, makes leakage structurally impossible for every
    downstream feature and prediction.
    """
    return [e for e in events if e.occurred_at <= asof]


def _items_asof(
    events: list[EventEnvelope], *, subject: UUID, topic_id: UUID, asof: datetime
) -> list[EvidenceItem]:
    windowed = events_asof(events, asof=asof)
    return collect_evidence(windowed, subject=subject, topic_id=topic_id)


# ---------------------------------------------------------------------------
# Feature value + vector.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FeatureValue:
    """One computed feature value with its full lineage.

    ``definition_key`` (name@version) names the EXACT definition that produced the
    value — a stored feature always reproduces, and a definition version bump is
    visible. ``evidence_event_ids`` carries the source events (lineage)."""

    name: str
    definition_key: str
    value: float
    dtype: str
    unit: str


@dataclass(frozen=True)
class FeatureVector:
    """The point-in-time feature vector for one (learner, topic) at ``asof``.

    Carries the values AND the lineage that produced them: the source event ids,
    the observation count, the registry signature, and ``asof`` — everything a
    prediction needs to be reproducible and to explain itself.
    """

    subject: UUID
    topic_id: UUID
    asof: datetime
    values: dict[str, FeatureValue]
    evidence_event_ids: list[UUID]
    observation_count: int
    registry_signature: str
    mastery_band: str
    mastery_plain_language: str

    def get(self, name: str) -> float:
        """Read one feature value by name. Raises ``KeyError`` for an unknown
        feature so a typo never silently returns 0."""
        if name not in self.values:
            raise KeyError(
                f"Feature '{name}' not present in vector. Available: "
                f"{sorted(self.values)}."
            )
        return self.values[name].value

    def as_dict(self) -> dict[str, float]:
        """Plain name -> value mapping (for the semantic layer / serialization)."""
        return {name: fv.value for name, fv in self.values.items()}


def compute_feature_vector(
    events: list[EventEnvelope],
    *,
    subject: UUID,
    topic_id: UUID,
    asof: datetime | None = None,
    weights: MasteryWeights | None = None,
    mastery: MasteryResult | None = None,
) -> FeatureVector:
    """Compute the point-in-time feature vector for one (learner, topic).

    ``asof`` defaults to now. The event list is filtered to ``asof`` FIRST, so no
    feature can see the future. The engine's mastery is computed over exactly the
    point-in-time window (or reused if supplied — it must have been computed at
    the same ``asof`` window) and shared with every definition.
    """
    asof = asof or _now_utc()
    windowed = events_asof(events, asof=asof)
    items = collect_evidence(windowed, subject=subject, topic_id=topic_id)
    if mastery is None:
        mastery = compute_mastery(
            windowed, subject=subject, topic_id=topic_id, weights=weights, asof=asof
        )

    inputs = FeatureInputs(
        subject=subject, topic_id=topic_id, asof=asof, items=items, mastery=mastery
    )

    values: dict[str, FeatureValue] = {}
    for d in all_definitions():
        raw = d.compute(inputs)
        values[d.name] = FeatureValue(
            name=d.name,
            definition_key=d.key,
            value=float(raw),
            dtype=d.dtype,
            unit=d.unit,
        )

    return FeatureVector(
        subject=subject,
        topic_id=topic_id,
        asof=asof,
        values=values,
        evidence_event_ids=[it.event_id for it in items],
        observation_count=len(items),
        registry_signature=registry_signature(),
        mastery_band=mastery.reading.band,
        mastery_plain_language=mastery.plain_language,
    )


def compute_single_feature(
    events: list[EventEnvelope],
    *,
    name: str,
    subject: UUID,
    topic_id: UUID,
    asof: datetime | None = None,
    weights: MasteryWeights | None = None,
) -> FeatureValue:
    """Compute exactly one feature by name, point-in-time. Convenience over
    ``compute_feature_vector`` that still goes through the single definition."""
    asof = asof or _now_utc()
    windowed = events_asof(events, asof=asof)
    items = collect_evidence(windowed, subject=subject, topic_id=topic_id)
    mastery = compute_mastery(
        windowed, subject=subject, topic_id=topic_id, weights=weights, asof=asof
    )
    d = get_definition(name)
    inputs = FeatureInputs(
        subject=subject, topic_id=topic_id, asof=asof, items=items, mastery=mastery
    )
    return FeatureValue(
        name=d.name,
        definition_key=d.key,
        value=float(d.compute(inputs)),
        dtype=d.dtype,
        unit=d.unit,
    )


# ---------------------------------------------------------------------------
# Per-learner feature snapshot across all touched topics.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LearnerFeatureSnapshot:
    """Every touched topic's point-in-time feature vector for one learner.

    A deterministic, idempotent projection: rebuilding from the same events at
    the same ``asof`` yields an identical snapshot. Keyed by opaque ids only.
    """

    subject: UUID
    asof: datetime
    vectors: dict[UUID, FeatureVector]
    registry_signature: str
    degraded_reasons: list[str] = field(default_factory=list)

    def vector(self, topic_id: UUID) -> FeatureVector | None:
        return self.vectors.get(topic_id)

    def topic_ids(self) -> list[UUID]:
        return sorted(self.vectors, key=str)


def _topics_touched_asof(
    events: list[EventEnvelope], *, subject: UUID, asof: datetime
) -> set[UUID]:
    """Topics the learner has any evidence on AT OR BEFORE ``asof``."""
    topics: set[UUID] = set()
    for env in events_asof(events, asof=asof):
        if env.canonical_uuid != subject:
            continue
        a = env.attempt()
        if a is not None:
            topics.add(a.ontology.topic_id)
            continue
        s = env.score()
        if s is not None and s.scored_subject == subject:
            topics.add(s.ontology.topic_id)
    return topics


def build_learner_snapshot(
    events: list[EventEnvelope],
    *,
    subject: UUID,
    asof: datetime | None = None,
    weights: MasteryWeights | None = None,
    degraded_reasons: list[str] | None = None,
) -> LearnerFeatureSnapshot:
    """Build the full point-in-time feature snapshot for one learner by replay.

    For every topic the learner has evidence on at ``asof``, compute its feature
    vector. Deterministic + idempotent: identical events + ``asof`` -> identical
    snapshot.
    """
    asof = asof or _now_utc()
    vectors: dict[UUID, FeatureVector] = {}
    for topic_id in sorted(
        _topics_touched_asof(events, subject=subject, asof=asof), key=str
    ):
        vectors[topic_id] = compute_feature_vector(
            events, subject=subject, topic_id=topic_id, asof=asof, weights=weights
        )
    return LearnerFeatureSnapshot(
        subject=subject,
        asof=asof,
        vectors=vectors,
        registry_signature=registry_signature(),
        degraded_reasons=degraded_reasons or [],
    )
