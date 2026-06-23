"""The learner-graph projection — the cohort-level view, built by replaying
events for many learners.

The learner graph (d14) composes individual learner profiles into a graph of
nodes (learners x topics) with mastery readings and confirmed gaps on the edges
to the ontology. This module builds that projection idempotently from a single
immutable event list and exposes the governed roll-ups the read views need:

  - per-topic cohort summaries (band distribution, confirmed-gap counts),
  - the set of learners with a confirmed gap of a given type on a topic.

INVARIANT 1 + 11: every node is keyed by the opaque ``canonical_uuid`` — no PII,
ever. Surfaces apply consent/purpose gating at READ time (the event store's
governed read functions); this projection assumes it was fed an already-gated
event list and adds no identity beyond the opaque token.

Pure and deterministic: same events -> same graph.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .gaps import GapResult
from .models import EventEnvelope, MasteryBand, MasteryWeights, PrerequisiteGraph, now_utc
from .profile import LearnerProfile, build_profile


def _subjects_in(events: list[EventEnvelope]) -> set[UUID]:
    """Every learner (opaque canonical_uuid) that appears in the event list."""
    return {env.canonical_uuid for env in events}


@dataclass(frozen=True)
class TopicCohortSummary:
    """Cohort roll-up for one topic, across all learners in the graph."""

    topic_id: UUID
    band_counts: dict[MasteryBand, int]
    confirmed_gap_counts: dict[str, int]
    learner_count: int


@dataclass(frozen=True)
class LearnerGraph:
    """The cohort-level projection: every learner's profile plus roll-ups."""

    profiles: dict[UUID, LearnerProfile]
    computed_at: datetime
    degraded_reasons: list[str] = field(default_factory=list)

    def profile(self, subject: UUID) -> LearnerProfile | None:
        return self.profiles.get(subject)

    def topic_ids(self) -> set[UUID]:
        out: set[UUID] = set()
        for prof in self.profiles.values():
            out.update(prof.topics.keys())
        return out

    def topic_summary(self, topic_id: UUID) -> TopicCohortSummary:
        bands: Counter[MasteryBand] = Counter()
        gap_counts: Counter[str] = Counter()
        learner_count = 0
        for prof in self.profiles.values():
            proj = prof.topic(topic_id)
            if proj is None:
                continue
            learner_count += 1
            bands[proj.mastery.reading.band] += 1
            for g in proj.confirmed_gaps:
                gap_counts[g.gap_type] += 1
        return TopicCohortSummary(
            topic_id=topic_id,
            band_counts=dict(bands),
            confirmed_gap_counts=dict(gap_counts),
            learner_count=learner_count,
        )

    def learners_with_confirmed_gap(self, topic_id: UUID, gap_type: str) -> list[UUID]:
        """Opaque ids of learners with a CONFIRMED gap of ``gap_type`` on the
        topic. The unit a proactive intervention (B7/A5) would act on — but the
        action itself sits behind the permission ladder, never here."""
        out: list[UUID] = []
        for subject, prof in self.profiles.items():
            proj = prof.topic(topic_id)
            if proj is None:
                continue
            if any(g.gap_type == gap_type for g in proj.confirmed_gaps):
                out.append(subject)
        out.sort(key=str)
        return out


def build_learner_graph(
    events: list[EventEnvelope],
    *,
    graph: PrerequisiteGraph | None = None,
    weights: MasteryWeights | None = None,
    asof: datetime | None = None,
    degraded_reasons: list[str] | None = None,
) -> LearnerGraph:
    """Replay the full event list into the cohort learner graph. Idempotent:
    the same events always produce the same graph."""
    asof = asof or now_utc()
    graph = graph or PrerequisiteGraph()
    profiles: dict[UUID, LearnerProfile] = {}
    for subject in sorted(_subjects_in(events), key=str):
        profiles[subject] = build_profile(
            events, subject=subject, graph=graph, weights=weights, asof=asof,
            degraded_reasons=degraded_reasons or [],
        )
    return LearnerGraph(profiles=profiles, computed_at=asof, degraded_reasons=degraded_reasons or [])
