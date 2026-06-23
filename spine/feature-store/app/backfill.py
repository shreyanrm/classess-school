"""Backfill — rebuild the feature store by REPLAYING an event list.

The whole feature store is a projection of the immutable event log; backfill is
how that projection is (re)materialized: feed an event list, replay it, produce a
snapshot of every learner's point-in-time feature vectors. Two laws govern it:

  - IDEMPOTENT: replaying the same events (at the same ``asof``) produces an
    identical result, every time. Re-running backfill is always safe — it cannot
    drift or double-count, because the projection is a pure function of the
    events. We assert this with a content signature.
  - POINT-IN-TIME CORRECT: every vector is computed against events filtered to
    ``asof`` — the rebuild never lets a learner's future leak into their past.

Because the projection is pure, "understanding of every past learner improves as
the models improve": bump a definition or the engine, re-run backfill over the
SAME old events, and every learner is re-understood with no new data. Backfill
also supports POINT-IN-TIME REPLAY: rebuild the feature set as it WOULD have
looked at a series of past ``asof`` instants — the training set for any model,
with no leakage by construction.

No external calls. With no event source configured, backfill runs over the
in-memory event list passed in (degraded, but bit-identical to the wired path).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .config import FeatureStoreSettings, get_settings
from .features import (
    LearnerFeatureSnapshot,
    build_learner_snapshot,
)
from .intelligence_interop import EventEnvelope, MasteryWeights
from .registry import registry_signature


def _now_utc() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


def _subjects_in(events: list[EventEnvelope]) -> list[UUID]:
    """Every learner (opaque canonical_uuid) in the event list, sorted for
    deterministic replay order."""
    return sorted({e.canonical_uuid for e in events}, key=str)


@dataclass(frozen=True)
class BackfillResult:
    """The materialized feature projection for a cohort at one ``asof``.

    Carries a deterministic ``content_signature`` over every value: two backfills
    of the same events at the same ``asof`` have equal signatures — the idempotence
    check made explicit and cheap to assert.
    """

    asof: datetime
    snapshots: dict[UUID, LearnerFeatureSnapshot]
    registry_signature: str
    event_count: int
    learner_count: int
    content_signature: str
    degraded_reasons: list[str] = field(default_factory=list)

    def snapshot(self, subject: UUID) -> LearnerFeatureSnapshot | None:
        return self.snapshots.get(subject)


def _content_signature(
    snapshots: dict[UUID, LearnerFeatureSnapshot], *, asof: datetime
) -> str:
    """A stable hash over the full feature content. Deterministic: independent of
    dict insertion order (keys are sorted) and float repr (rounded). Equal inputs
    -> equal signature, which is exactly the idempotence guarantee."""
    payload: list = [registry_signature(), asof.isoformat()]
    for subject in sorted(snapshots, key=str):
        snap = snapshots[subject]
        for topic_id in snap.topic_ids():
            vec = snap.vectors[topic_id]
            row = [
                str(subject),
                str(topic_id),
                vec.asof.isoformat(),
                vec.observation_count,
                # event ids in their lineage order
                [str(e) for e in vec.evidence_event_ids],
                # rounded values keyed by definition key (name@version)
                {
                    fv.definition_key: round(fv.value, 9)
                    for fv in sorted(vec.values.values(), key=lambda f: f.name)
                },
            ]
            payload.append(row)
    blob = json.dumps(payload, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def backfill(
    events: list[EventEnvelope],
    *,
    asof: datetime | None = None,
    subjects: list[UUID] | None = None,
    weights: MasteryWeights | None = None,
    settings: FeatureStoreSettings | None = None,
) -> BackfillResult:
    """Rebuild the feature store for ``asof`` by replaying ``events``.

    For every learner in the list (or the given ``subjects`` subset), build the
    point-in-time feature snapshot across all topics they have evidence on at
    ``asof``. Pure, deterministic, idempotent — re-running yields an identical
    ``content_signature``.
    """
    settings = settings or get_settings()
    asof = asof or _now_utc()
    degraded = settings.degraded_reasons()

    target_subjects = subjects if subjects is not None else _subjects_in(events)
    target_subjects = sorted(set(target_subjects), key=str)

    snapshots: dict[UUID, LearnerFeatureSnapshot] = {}
    for subject in target_subjects:
        snapshots[subject] = build_learner_snapshot(
            events, subject=subject, asof=asof, weights=weights, degraded_reasons=degraded
        )

    return BackfillResult(
        asof=asof,
        snapshots=snapshots,
        registry_signature=registry_signature(),
        event_count=len(events),
        learner_count=len(snapshots),
        content_signature=_content_signature(snapshots, asof=asof),
        degraded_reasons=degraded,
    )


def is_idempotent(
    events: list[EventEnvelope],
    *,
    asof: datetime | None = None,
    subjects: list[UUID] | None = None,
    weights: MasteryWeights | None = None,
    settings: FeatureStoreSettings | None = None,
) -> bool:
    """Replay twice and confirm the content signatures match. A guard a caller
    (or a test) can assert; the property is structural, this just verifies it."""
    a = backfill(events, asof=asof, subjects=subjects, weights=weights, settings=settings)
    b = backfill(events, asof=asof, subjects=subjects, weights=weights, settings=settings)
    return a.content_signature == b.content_signature


def backfill_point_in_time_series(
    events: list[EventEnvelope],
    *,
    asofs: list[datetime],
    subjects: list[UUID] | None = None,
    weights: MasteryWeights | None = None,
    settings: FeatureStoreSettings | None = None,
) -> dict[datetime, BackfillResult]:
    """Rebuild the feature set as it WOULD have looked at each ``asof`` instant.

    The training-set builder: each result sees ONLY events up to its ``asof`` (no
    future leakage), so the series is a leak-free, point-in-time-correct history.
    Deterministic and idempotent per instant.
    """
    out: dict[datetime, BackfillResult] = {}
    for asof in sorted(asofs):
        out[asof] = backfill(
            events, asof=asof, subjects=subjects, weights=weights, settings=settings
        )
    return out
