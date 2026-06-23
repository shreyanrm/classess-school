"""Point-in-time correctness — no future leakage, ever.

The defining property of a leak-free feature store: a feature computed AS OF a
past instant must depend ONLY on events that occurred at or before that instant.
A later event can never reach back and change a past feature value. These tests
prove that structurally.
"""

from __future__ import annotations

from app.backfill import backfill_point_in_time_series
from app.features import compute_feature_vector, events_asof

from .conftest import (
    LEARNER_A,
    NOW,
    T_FUNDTHM,
    days_ago,
    indep,
)


def _history():
    # Three independent successes spread over time.
    return [
        indep(LEARNER_A, T_FUNDTHM, correct=True, score=0.7, occurred_at=days_ago(20)),
        indep(LEARNER_A, T_FUNDTHM, correct=True, score=0.8, occurred_at=days_ago(10)),
        indep(LEARNER_A, T_FUNDTHM, correct=True, score=0.9, occurred_at=days_ago(2)),
    ]


def test_events_asof_excludes_the_future():
    events = _history()
    early = events_asof(events, asof=days_ago(15))
    assert len(early) == 1  # only the day-20 event
    mid = events_asof(events, asof=days_ago(5))
    assert len(mid) == 2
    full = events_asof(events, asof=NOW)
    assert len(full) == 3


def test_past_feature_ignores_later_events():
    """A vector AS OF day-15 must be identical whether or not later events exist
    in the input list — the future is invisible to the past."""
    events = _history()
    only_past = [e for e in events if e.occurred_at <= days_ago(15)]

    asof = days_ago(15)
    with_future = compute_feature_vector(events, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=asof)
    without_future = compute_feature_vector(only_past, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=asof)

    assert with_future.as_dict() == without_future.as_dict()
    assert with_future.evidence_event_ids == without_future.evidence_event_ids
    assert with_future.observation_count == 1


def test_observation_count_grows_monotonically_over_time():
    """As asof advances, the point-in-time observation count only ever grows —
    evidence accumulates, it never time-travels."""
    events = _history()
    counts = []
    for d in (25, 15, 5, 0):
        vec = compute_feature_vector(events, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=days_ago(d))
        counts.append(vec.observation_count)
    assert counts == sorted(counts)
    assert counts == [0, 1, 2, 3]


def test_adding_a_future_event_does_not_mutate_a_past_vector():
    """Appending a brand-new event after ``asof`` leaves every earlier
    point-in-time vector byte-identical — the leakage guard under append."""
    events = _history()
    asof = days_ago(5)
    before = compute_feature_vector(events, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=asof)

    augmented = events + [indep(LEARNER_A, T_FUNDTHM, correct=True, score=1.0, occurred_at=NOW)]
    after = compute_feature_vector(augmented, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=asof)

    assert before.as_dict() == after.as_dict()
    assert before.evidence_event_ids == after.evidence_event_ids


def test_point_in_time_series_is_leak_free():
    """The training-set builder: each asof slice sees only its own past."""
    events = _history()
    asofs = [days_ago(25), days_ago(15), days_ago(5), NOW]
    series = backfill_point_in_time_series(events, asofs=asofs, subjects=[LEARNER_A])

    counts = []
    for asof in asofs:
        snap = series[asof].snapshot(LEARNER_A)
        vec = snap.vector(T_FUNDTHM)
        n = 0 if vec is None else vec.observation_count
        counts.append(n)
    assert counts == [0, 1, 2, 3]

    # The day-15 slice's lineage is a strict subset of the NOW slice's lineage.
    mid_vec = series[days_ago(15)].snapshot(LEARNER_A).vector(T_FUNDTHM)
    now_vec = series[NOW].snapshot(LEARNER_A).vector(T_FUNDTHM)
    assert set(mid_vec.evidence_event_ids) < set(now_vec.evidence_event_ids)
