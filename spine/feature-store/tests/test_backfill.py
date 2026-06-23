"""Backfill: deterministic + idempotent rebuild by replaying events.

The spine A3 guarantee: derived stores are projections of the immutable events.
Re-running backfill must be a safe, drift-free no-op on the content — proven via
the content signature — and must let old learners be re-understood as the models
improve, all without leakage.
"""

from __future__ import annotations

from app.backfill import backfill, is_idempotent

from .conftest import (
    LEARNER_A,
    LEARNER_B,
    NOW,
    T_FUNDTHM,
    T_TRIG_RATIOS,
    days_ago,
    indep,
)


def _cohort(improving_history, declining_history):
    return improving_history + declining_history


def test_backfill_is_deterministic(improving_history, declining_history):
    events = _cohort(improving_history, declining_history)
    a = backfill(events, asof=NOW)
    b = backfill(events, asof=NOW)
    assert a.content_signature == b.content_signature
    assert a.learner_count == 2
    assert set(a.snapshots) == {LEARNER_A, LEARNER_B}


def test_backfill_idempotent_under_shuffled_input(improving_history, declining_history):
    """Replaying the SAME events in a different input order yields an identical
    projection signature — order independence is part of idempotence."""
    events = _cohort(improving_history, declining_history)
    a = backfill(events, asof=NOW)
    b = backfill(list(reversed(events)), asof=NOW)
    assert a.content_signature == b.content_signature


def test_is_idempotent_helper(improving_history, declining_history):
    events = _cohort(improving_history, declining_history)
    assert is_idempotent(events, asof=NOW) is True


def test_backfill_subset_of_subjects(improving_history, declining_history):
    events = _cohort(improving_history, declining_history)
    only_a = backfill(events, asof=NOW, subjects=[LEARNER_A])
    assert only_a.learner_count == 1
    assert set(only_a.snapshots) == {LEARNER_A}
    # The single-subject signature differs from the whole-cohort one.
    full = backfill(events, asof=NOW)
    assert only_a.content_signature != full.content_signature


def test_backfill_carries_degraded_reasons_by_name(improving_history):
    """With no event source / gateway configured the rebuild still runs and names
    (never values) the env vars that would lift degradation."""
    res = backfill(improving_history, asof=NOW)
    reasons = res.snapshots[LEARNER_A].degraded_reasons
    # Names only — never a secret value.
    assert "clss.feature-store.dev.database_url" in res.degraded_reasons
    assert "clss.feature-store.dev.gateway_url" in res.degraded_reasons
    assert reasons == res.degraded_reasons
    for r in res.degraded_reasons:
        assert r.startswith("clss.feature-store.dev.")


def test_backfill_point_in_time_differs_across_asof():
    """Backfilling at two instants yields different signatures when evidence has
    accumulated between them — and the earlier one cannot see the later events."""
    events = [
        indep(LEARNER_A, T_FUNDTHM, correct=True, score=0.7, occurred_at=days_ago(20)),
        indep(LEARNER_A, T_FUNDTHM, correct=True, score=0.9, occurred_at=days_ago(2)),
    ]
    early = backfill(events, asof=days_ago(10))
    late = backfill(events, asof=NOW)
    assert early.content_signature != late.content_signature
    early_snap = early.snapshot(LEARNER_A)
    # At day-10 only the first event is visible.
    assert early_snap.vector(T_FUNDTHM).observation_count == 1
    assert late.snapshot(LEARNER_A).vector(T_FUNDTHM).observation_count == 2


def test_remodeling_old_events_reproduces_when_unchanged(improving_history):
    """Re-running the current models over the same old events reproduces exactly
    — the substrate for 'understanding improves as models improve' (a model bump
    changes this; an unchanged model must not)."""
    first = backfill(improving_history, asof=NOW)
    second = backfill(improving_history, asof=NOW)
    assert first.content_signature == second.content_signature
    assert first.registry_signature == second.registry_signature
