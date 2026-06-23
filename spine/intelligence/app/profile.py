"""The learner profile — the evidence-linked mastery/gap projection for one
learner, built by REPLAYING events.

A profile is a PROJECTION, never authored directly: ``build_profile`` takes an
immutable event list and produces, per touched topic, the mastery reading and
the detected gaps, each carrying its lineage (the source event ids). Rebuilding
from the same event list yields an identical profile — idempotent by
construction, which is what lets "understanding of every past learner improve as
the models improve": re-run the new model over the old events.

The profile is PII-free: keyed by the opaque ``canonical_uuid`` and opaque
topic ids only. Surfaces read ``plain_language`` and the dimension breakdown;
they never see the composite number or the formula.

The freshness guard (``build_profile`` honoring ``last_projected_at``) means a
rebuild only changes a topic's entry when fresh evidence has arrived.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .evidence import collect_evidence, has_fresh_evidence, topics_with_evidence
from .gaps import GapResult, detect_gaps
from .mastery import MasteryResult, compute_mastery
from .models import EventEnvelope, MasteryWeights, PrerequisiteGraph, now_utc


@dataclass(frozen=True)
class TopicProjection:
    """One topic's derived state with lineage."""

    topic_id: UUID
    mastery: MasteryResult
    gaps: list[GapResult]
    last_evidence_at: datetime | None

    @property
    def confirmed_gaps(self) -> list[GapResult]:
        return [g for g in self.gaps if g.confirmed]

    @property
    def plain_language(self) -> str:
        return self.mastery.plain_language


@dataclass(frozen=True)
class LearnerProfile:
    """The full per-learner projection. Keyed by opaque canonical_uuid only."""

    subject: UUID
    topics: dict[UUID, TopicProjection]
    computed_at: datetime
    # Names (never values) of env vars whose absence kept the engine degraded.
    degraded_reasons: list[str] = field(default_factory=list)

    def topic(self, topic_id: UUID) -> TopicProjection | None:
        return self.topics.get(topic_id)

    def all_confirmed_gaps(self) -> list[GapResult]:
        out: list[GapResult] = []
        for proj in self.topics.values():
            out.extend(proj.confirmed_gaps)
        return out


def build_topic_projection(
    events: list[EventEnvelope],
    *,
    subject: UUID,
    topic_id: UUID,
    graph: PrerequisiteGraph | None = None,
    weights: MasteryWeights | None = None,
    asof: datetime | None = None,
) -> TopicProjection:
    """Derive one topic's mastery + gaps by replay. Computes mastery once and
    feeds it into the gap engine so the two agree."""
    asof = asof or now_utc()
    graph = graph or PrerequisiteGraph()
    items = collect_evidence(events, subject=subject, topic_id=topic_id)
    mastery = compute_mastery(events, subject=subject, topic_id=topic_id, weights=weights, asof=asof)
    gaps = detect_gaps(
        events, subject=subject, topic_id=topic_id,
        graph=graph, weights=weights, asof=asof, mastery=mastery,
    )
    last_at = max((it.occurred_at for it in items), default=None)
    return TopicProjection(topic_id=topic_id, mastery=mastery, gaps=gaps, last_evidence_at=last_at)


def build_profile(
    events: list[EventEnvelope],
    *,
    subject: UUID,
    graph: PrerequisiteGraph | None = None,
    weights: MasteryWeights | None = None,
    asof: datetime | None = None,
    last_projected_at: datetime | None = None,
    previous: LearnerProfile | None = None,
    degraded_reasons: list[str] | None = None,
) -> LearnerProfile:
    """Build (or idempotently rebuild) a learner profile from an event list.

    For every topic the learner has evidence on, derive its projection. When
    ``last_projected_at``/``previous`` are supplied, topics with NO fresh
    evidence since the last projection are carried over unchanged (the profile
    updates ONLY on fresh evidence). A full rebuild (no ``previous``) recomputes
    everything and is deterministic.
    """
    asof = asof or now_utc()
    graph = graph or PrerequisiteGraph()
    topics: dict[UUID, TopicProjection] = {}

    for topic_id in topics_with_evidence(events, subject=subject):
        items = collect_evidence(events, subject=subject, topic_id=topic_id)
        if previous is not None and not has_fresh_evidence(items, last_projected_at=last_projected_at):
            carried = previous.topic(topic_id)
            if carried is not None:
                topics[topic_id] = carried
                continue
        topics[topic_id] = build_topic_projection(
            events, subject=subject, topic_id=topic_id, graph=graph, weights=weights, asof=asof,
        )

    return LearnerProfile(
        subject=subject,
        topics=topics,
        computed_at=asof,
        degraded_reasons=degraded_reasons or [],
    )
