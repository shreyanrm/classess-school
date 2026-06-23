"""The evidence layer: weighting, freshness, lineage.

Every mastery reading and every gap classification in this engine is built from
a concrete set of evidence rows and carries their ids back out (lineage). This
module owns:

  - ``EvidenceItem``: a single normalized observation derived from one event,
    keeping a back-reference to the source ``event_id``.
  - the evidence WEIGHTING: how much a single observation counts (recency decay,
    assistance level, difficulty, evaluator confidence) — deterministic.
  - ``collect_evidence``: turn an event list for one (learner, topic) into the
    ordered evidence trail the dimensions and gap rules consume.
  - the FRESHNESS guard: the profile updates ONLY when new events have arrived
    since the last projection (``has_fresh_evidence``), so a rebuild is a no-op
    when nothing changed and a single stale read can never re-confirm a gap.

No external calls. Pure functions over the replayed event list.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from .models import AttemptPayload, EventEnvelope, ScoreRecordedPayload

# Half-life for recency decay. An observation this old counts half as much.
# Links to the retention gap: evidence past a few half-lives is nearly weightless.
RECENCY_HALF_LIFE = timedelta(days=21)

# How much weight a supported attempt's CORRECTNESS contributes versus an
# independent one. Supported success is real evidence (the learner engaged and
# produced) but it is NOT evidence of independent capability — the Independence
# dimension is where that distinction is made sharp; here we only soften the
# generic weight so an all-supported history cannot read as full mastery.
SUPPORTED_WEIGHT = 0.6
INDEPENDENT_WEIGHT = 1.0

# Assistance ladder ordered most-support -> none. Lower index = more help.
_ASSISTANCE_ORDER = {
    "Learn": 0,
    "Coach": 1,
    "Hint": 2,
    "Work-with-me": 3,
    "Check-my-work": 4,
    "Independent": 5,
}

# Evaluator-confidence multipliers for score.recorded corroboration.
_CONFIDENCE_BAND_WEIGHT = {"low": 0.4, "medium": 0.7, "high": 1.0}


@dataclass(frozen=True)
class EvidenceItem:
    """One normalized observation, with a back-reference to its source event.

    This is the unit of LINEAGE: every dimension value and every gap rationale
    can name the ``event_id`` set it was computed from.
    """

    event_id: UUID
    occurred_at: datetime
    topic_id: UUID
    # Normalized success in [0,1] (partial credit honored).
    score: float
    correct: bool
    # The keystone flag, propagated from the attempt.
    independent: bool
    assistance_level: str
    difficulty: float
    time_taken_ms: int | None
    # Where the observation came from, for explainability.
    source: str  # "attempt" | "score"
    # Evaluator confidence band for score events; None for attempts.
    confidence_band: str | None = None
    attempt_number: int = 1

    def recency_weight(self, *, asof: datetime) -> float:
        """Exponential decay by age. 1.0 fresh, 0.5 at one half-life, ->0 old."""
        age = asof - self.occurred_at
        age_days = max(age.total_seconds(), 0.0) / 86400.0
        half_life_days = RECENCY_HALF_LIFE.total_seconds() / 86400.0
        return 0.5 ** (age_days / half_life_days)

    def base_weight(self) -> float:
        """Static weight independent of time: mode + evaluator confidence."""
        w = INDEPENDENT_WEIGHT if self.independent else SUPPORTED_WEIGHT
        if self.confidence_band is not None:
            w *= _CONFIDENCE_BAND_WEIGHT.get(self.confidence_band, 0.7)
        return w

    def weight(self, *, asof: datetime) -> float:
        """Full evidence weight = base x recency. Used to combine observations."""
        return self.base_weight() * self.recency_weight(asof=asof)


def assistance_rank(level: str) -> int:
    """Position on the assistance ladder (0 = most support, 5 = none)."""
    return _ASSISTANCE_ORDER.get(level, 0)


def _attempt_to_item(env: EventEnvelope, a: AttemptPayload) -> EvidenceItem:
    return EvidenceItem(
        event_id=env.event_id,
        occurred_at=env.occurred_at,
        topic_id=a.ontology.topic_id,
        score=a.effective_score,
        correct=a.correct,
        independent=(a.mode == "independent"),
        assistance_level=a.assistance_level,
        difficulty=a.difficulty,
        time_taken_ms=a.time_taken_ms,
        source="attempt",
        attempt_number=a.attempt_number,
    )


def _score_to_item(env: EventEnvelope, s: ScoreRecordedPayload) -> EvidenceItem:
    # A recorded score is corroborating evidence. It carries no independence
    # signal of its own, so it is treated as a supported observation for the
    # Independence dimension (it cannot lift independence), but it DOES count as
    # a second, fresh signal for gap corroboration and reassessment.
    return EvidenceItem(
        event_id=env.event_id,
        occurred_at=env.occurred_at,
        topic_id=s.ontology.topic_id,
        score=s.raw_score,
        correct=s.raw_score >= 0.5,
        independent=False,
        assistance_level="Check-my-work",
        difficulty=0.5,
        time_taken_ms=None,
        source="score",
        confidence_band=s.confidence_band,
    )


def collect_evidence(
    events: list[EventEnvelope],
    *,
    subject: UUID,
    topic_id: UUID,
) -> list[EvidenceItem]:
    """Replay the event list into the ordered evidence trail for one
    (learner, topic). Filters by canonical_uuid + topic, honors purpose, and
    sorts chronologically by ``occurred_at`` so the projection is deterministic.

    The same input list always yields the same trail — the basis of idempotent
    rebuilds.
    """
    items: list[EvidenceItem] = []
    for env in events:
        if env.canonical_uuid != subject:
            continue
        a = env.attempt()
        if a is not None and a.ontology.topic_id == topic_id:
            items.append(_attempt_to_item(env, a))
            continue
        s = env.score()
        if s is not None and s.scored_subject == subject and s.ontology.topic_id == topic_id:
            items.append(_score_to_item(env, s))
    items.sort(key=lambda it: (it.occurred_at, str(it.event_id)))
    return items


def topics_with_evidence(events: list[EventEnvelope], *, subject: UUID) -> set[UUID]:
    """Every topic the learner has any evidence on. Used to drive a profile
    rebuild across all touched topics."""
    topics: set[UUID] = set()
    for env in events:
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


def latest_evidence_time(items: list[EvidenceItem]) -> datetime | None:
    if not items:
        return None
    return max(it.occurred_at for it in items)


def has_fresh_evidence(
    items: list[EvidenceItem],
    *,
    last_projected_at: datetime | None,
) -> bool:
    """The profile updates ONLY on fresh evidence. True when there is at least
    one observation newer than the last projection (or no projection yet)."""
    latest = latest_evidence_time(items)
    if latest is None:
        return False
    if last_projected_at is None:
        return True
    return latest > last_projected_at


def lineage_ids(items: list[EvidenceItem]) -> list[UUID]:
    """The full, de-duplicated, ordered list of source event ids — the lineage
    attached to a conclusion. Never an opaque claim."""
    seen: dict[UUID, None] = {}
    for it in items:
        seen.setdefault(it.event_id, None)
    return list(seen.keys())
