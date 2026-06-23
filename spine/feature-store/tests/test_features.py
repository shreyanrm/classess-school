"""Feature store: determinism, idempotence, definition discipline, lineage.

These guard the spine A3 promise that derived stores are pure projections of the
immutable events — rebuildable, reproducible, and never authored directly.
"""

from __future__ import annotations

from app.features import (
    build_learner_snapshot,
    compute_feature_vector,
    compute_single_feature,
)
from app.registry import (
    all_definitions,
    feature_names,
    get_definition,
    registry_signature,
)

from .conftest import (
    LEARNER_A,
    NOW,
    T_FUNDTHM,
)


def test_registry_is_single_source(improving_history):
    """Every definition is unique and reachable; the vector contains exactly the
    registered features — one definition, computed the same everywhere."""
    names = feature_names()
    assert len(names) == len(set(names)), "duplicate feature names in the registry"
    vec = compute_feature_vector(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    assert set(vec.values) == set(names)
    for d in all_definitions():
        assert vec.values[d.name].definition_key == d.key
        # value carried under the SAME definition the registry exposes
        assert get_definition(d.name) is d


def test_unknown_feature_fails_loudly():
    import pytest

    with pytest.raises(KeyError):
        get_definition("not_a_real_feature")


def test_feature_vector_is_deterministic(improving_history):
    """Same events + same asof -> identical vector, value for value."""
    a = compute_feature_vector(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    b = compute_feature_vector(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    assert a.as_dict() == b.as_dict()
    assert a.evidence_event_ids == b.evidence_event_ids
    assert a.registry_signature == b.registry_signature


def test_event_order_does_not_change_features(improving_history):
    """The engine sorts the trail deterministically, so shuffling the INPUT event
    order must not change any feature value (idempotent projection)."""
    forward = compute_feature_vector(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    reversed_events = list(reversed(improving_history))
    backward = compute_feature_vector(reversed_events, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    assert forward.as_dict() == backward.as_dict()
    # Lineage is the SAME SET of source events regardless of input order.
    assert set(forward.evidence_event_ids) == set(backward.evidence_event_ids)


def test_single_feature_matches_vector(improving_history):
    """A single-feature compute goes through the same definition as the vector."""
    vec = compute_feature_vector(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    single = compute_single_feature(
        improving_history, name="independent_success_rate", subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW
    )
    assert single.value == vec.get("independent_success_rate")
    assert single.definition_key == vec.values["independent_success_rate"].definition_key


def test_features_carry_lineage(improving_history):
    """Every vector names the exact source events it was computed from."""
    vec = compute_feature_vector(improving_history, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    assert vec.observation_count == len(vec.evidence_event_ids)
    assert vec.observation_count == 6
    # ids are real engine event ids drawn from the input list.
    input_ids = {e.event_id for e in improving_history}
    assert set(vec.evidence_event_ids).issubset(input_ids)


def test_independence_is_capped_for_supported_only():
    """An all-supported success history reads with low independent_success_rate —
    the keystone read inherited from the engine, surfaced as a feature."""
    from .conftest import supported

    events = [
        supported(LEARNER_A, T_FUNDTHM, correct=True, score=1.0),
        supported(LEARNER_A, T_FUNDTHM, correct=True, score=1.0),
        supported(LEARNER_A, T_FUNDTHM, correct=True, score=1.0),
    ]
    vec = compute_feature_vector(events, subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    assert vec.get("independent_success_rate") == 0.0
    assert vec.get("overall_success_rate") > 0.0
    assert vec.get("independent_attempt_count") == 0.0


def test_empty_history_is_safe():
    """No evidence -> a well-formed empty vector, not a crash."""
    vec = compute_feature_vector([], subject=LEARNER_A, topic_id=T_FUNDTHM, asof=NOW)
    assert vec.observation_count == 0
    assert vec.get("observation_count") == 0.0
    assert vec.get("independent_success_rate") == 0.0
    assert vec.mastery_band == "not-started"


def test_learner_snapshot_covers_touched_topics(improving_history, declining_history):
    """A snapshot has one vector per topic the learner touched, and is keyed by
    opaque ids only."""
    snap = build_learner_snapshot(improving_history, subject=LEARNER_A, asof=NOW)
    assert snap.subject == LEARNER_A
    assert T_FUNDTHM in snap.vectors
    assert snap.topic_ids() == [T_FUNDTHM]
    assert snap.registry_signature == registry_signature()


def test_snapshot_rebuild_is_idempotent(improving_history):
    """Rebuilding the snapshot from the same events yields identical content."""
    a = build_learner_snapshot(improving_history, subject=LEARNER_A, asof=NOW)
    b = build_learner_snapshot(improving_history, subject=LEARNER_A, asof=NOW)
    assert a.topic_ids() == b.topic_ids()
    for t in a.topic_ids():
        assert a.vectors[t].as_dict() == b.vectors[t].as_dict()
