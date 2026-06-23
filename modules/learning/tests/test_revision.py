"""Spaced retrieval against the forgetting curve."""

from __future__ import annotations

from learning import revision
from learning.revision import RetrievalObservation, schedule_topic

from .conftest import NOW, days_ago


def _obs(n, success=True, independent=True, score=None):
    return RetrievalObservation(occurred_at=days_ago(n), success=success, independent=independent, score=score)


def test_no_evidence_is_not_on_the_plan():
    sch = schedule_topic(topic_id="t1", observations=[], asof=NOW)
    assert sch.due_at is None
    assert not sch.is_due
    assert "yet" in sch.plain_language


def test_retention_decays_over_time():
    # A single recent success vs the same success long ago: the old one has lower
    # predicted retention now.
    fresh = schedule_topic(topic_id="t1", observations=[_obs(1)], asof=NOW)
    stale = schedule_topic(topic_id="t1", observations=[_obs(120)], asof=NOW)
    assert fresh.retention_now > stale.retention_now


def test_spaced_independent_successes_grow_stability():
    massed = schedule_topic(topic_id="t1", observations=[_obs(3), _obs(2), _obs(1)], asof=NOW)
    spaced = schedule_topic(topic_id="t1", observations=[_obs(40), _obs(20), _obs(5)], asof=NOW)
    # Spacing effect: well-spaced retrievals build more durable memory.
    assert spaced.stability_days > massed.stability_days


def test_independent_consolidates_more_than_supported():
    indep = schedule_topic(topic_id="t1", observations=[_obs(20, independent=True), _obs(5, independent=True)], asof=NOW)
    supp = schedule_topic(topic_id="t1", observations=[_obs(20, independent=False), _obs(5, independent=False)], asof=NOW)
    assert indep.stability_days > supp.stability_days


def test_failed_recall_resets_and_is_due_now():
    obs = [_obs(40), _obs(20), _obs(10), _obs(1, success=False, score=0.1)]
    sch = schedule_topic(topic_id="t1", observations=obs, asof=NOW)
    assert sch.is_due
    assert sch.stability_days == revision.MIN_STABILITY_DAYS
    assert sch.plain_language == "revision is due"


def test_due_when_retention_drops_to_target():
    # A long-ago single success will have decayed past the target retrievability.
    sch = schedule_topic(topic_id="t1", observations=[_obs(90)], asof=NOW)
    assert sch.is_due
    assert sch.plain_language == "revision is due"


def test_due_topics_orders_most_decayed_first():
    a = schedule_topic(topic_id="a", observations=[_obs(120)], asof=NOW)
    b = schedule_topic(topic_id="b", observations=[_obs(200)], asof=NOW)
    fresh = schedule_topic(topic_id="c", observations=[_obs(1)], asof=NOW)
    due = revision.due_topics([fresh, a, b], asof=NOW)
    assert [s.topic_id for s in due] == ["b", "a"]  # fresh not due; b most decayed


def test_deterministic_same_inputs_same_schedule():
    obs = [_obs(30), _obs(10), _obs(2)]
    a = schedule_topic(topic_id="t1", observations=obs, asof=NOW)
    b = schedule_topic(topic_id="t1", observations=obs, asof=NOW)
    assert a == b
