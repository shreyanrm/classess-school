"""Profile + learner-graph projection tests — idempotent rebuild from events,
the fresh-evidence guard, lineage, and cohort roll-ups."""

from __future__ import annotations

from app.config import IntelligenceSettings
from app.graph import build_learner_graph
from app.profile import build_profile
from app.source import InMemoryEventSource, make_event_source

from .conftest import (
    LEARNER_A,
    LEARNER_B,
    NOW,
    T_EUCLID,
    T_FUNDTHM,
    days_ago,
    indep,
    supported,
)


def test_profile_rebuild_is_idempotent():
    events = [
        indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(i)) for i in range(4)
    ] + [
        supported(LEARNER_A, T_FUNDTHM, correct=True, occurred_at=days_ago(i)) for i in range(3)
    ]
    a = build_profile(events, subject=LEARNER_A, asof=NOW)
    b = build_profile(list(reversed(events)), subject=LEARNER_A, asof=NOW)
    assert set(a.topics) == set(b.topics)
    for tid in a.topics:
        assert a.topic(tid).mastery.reading.model_dump() == b.topic(tid).mastery.reading.model_dump()


def test_profile_covers_every_touched_topic_with_lineage():
    events = [
        indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(2)),
        indep(LEARNER_A, T_FUNDTHM, correct=True, occurred_at=days_ago(1)),
    ]
    prof = build_profile(events, subject=LEARNER_A, asof=NOW)
    assert set(prof.topics) == {T_EUCLID, T_FUNDTHM}
    for proj in prof.topics.values():
        assert proj.mastery.evidence_event_ids, "every projection must carry lineage"


def test_fresh_evidence_guard_carries_unchanged_topics():
    """A rebuild only changes a topic when fresh evidence has arrived since the
    last projection; stale topics are carried over unchanged."""
    old_events = [indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(10)) for _ in range(3)]
    first = build_profile(old_events, subject=LEARNER_A, asof=days_ago(9))

    # New evidence on a DIFFERENT topic; T_EUCLID unchanged.
    new_events = old_events + [indep(LEARNER_A, T_FUNDTHM, correct=True, occurred_at=days_ago(1))]
    second = build_profile(
        new_events, subject=LEARNER_A, asof=NOW,
        previous=first, last_projected_at=days_ago(9),
    )
    # T_EUCLID projection object is carried over verbatim (no fresh evidence).
    assert second.topic(T_EUCLID) is first.topic(T_EUCLID)
    # T_FUNDTHM is newly computed.
    assert second.topic(T_FUNDTHM) is not None


def test_learner_graph_rolls_up_cohort():
    events = (
        [indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(i), difficulty=0.6) for i in range(5)]
        + [supported(LEARNER_B, T_EUCLID, correct=True, assistance_level="Coach", occurred_at=days_ago(i)) for i in range(4)]
        + [indep(LEARNER_B, T_EUCLID, correct=False, score=0.2, occurred_at=days_ago(1))]
    )
    g = build_learner_graph(events, asof=NOW)
    assert set(g.profiles) == {LEARNER_A, LEARNER_B}
    summary = g.topic_summary(T_EUCLID)
    assert summary.learner_count == 2
    assert sum(summary.band_counts.values()) == 2
    # Learner B (supported-only success then independent fail) should show a
    # support-dependency confirmed gap; Learner A should not.
    dependents = g.learners_with_confirmed_gap(T_EUCLID, "support-dependency")
    assert LEARNER_B in dependents
    assert LEARNER_A not in dependents


def test_learner_graph_is_deterministic():
    events = [indep(LEARNER_A, T_EUCLID, correct=True, occurred_at=days_ago(i)) for i in range(3)]
    g1 = build_learner_graph(events, asof=NOW)
    g2 = build_learner_graph(list(reversed(events)), asof=NOW)
    s1 = g1.topic_summary(T_EUCLID)
    s2 = g2.topic_summary(T_EUCLID)
    assert s1.band_counts == s2.band_counts


def test_source_degrades_to_in_memory_when_unset(monkeypatch):
    monkeypatch.delenv("CLSS_INTELLIGENCE_DEV_DATABASE_URL", raising=False)
    settings = IntelligenceSettings()
    src = make_event_source(settings)
    assert isinstance(src, InMemoryEventSource)
    assert "degraded" in src.backend
    assert settings.has_event_source is False
    assert "clss.intelligence.dev.database_url" in settings.degraded_reasons()


def test_in_memory_source_filters_by_subject():
    src = InMemoryEventSource([
        indep(LEARNER_A, T_EUCLID, correct=True),
        indep(LEARNER_B, T_EUCLID, correct=True),
    ])
    assert len(src.read_events(subject=LEARNER_A)) == 1
    assert len(src.read_events()) == 2
