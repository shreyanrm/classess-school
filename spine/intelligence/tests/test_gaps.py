"""Gap engine tests — the ten types, each with its own rule; the CORE guarantee
that a gap is NEVER confirmed from a single bad score; corroboration and
reassessment behavior."""

from __future__ import annotations

from app.gaps import detect_gaps

from .conftest import (
    LEARNER_A,
    NOW,
    T_EUCLID,
    T_FUNDTHM,
    T_IRRATIONAL,
    days_ago,
    indep,
    score_event,
    supported,
)


def _by_type(results):
    return {r.gap_type: r for r in results}


def test_single_bad_score_does_not_confirm_a_gap():
    """CORE invariant: one bad score is a signal, never a confirmed gap."""
    events = [indep(LEARNER_A, T_EUCLID, correct=False, score=0.1, difficulty=0.4)]
    results = detect_gaps(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    for r in results:
        assert r.confirmed is False, f"{r.gap_type} must not be confirmed from one score"
        assert r.signal_count < 2


def test_two_corroborating_bad_scores_confirm_a_gap():
    events = [
        supported(LEARNER_A, T_EUCLID, correct=False, score=0.1, assistance_level="Coach", occurred_at=days_ago(2)),
        supported(LEARNER_A, T_EUCLID, correct=False, score=0.15, assistance_level="Coach", occurred_at=days_ago(1)),
    ]
    results = detect_gaps(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    confirmed = [r for r in results if r.confirmed]
    assert confirmed, "two corroborating weak signals should confirm at least one gap"
    assert all(len(r.evidence.evidence_event_ids) >= 1 for r in results)


def test_reassessment_clears_the_gap():
    """THE LOOP: weak, then strong independent reassessment -> no confirmed gap."""
    events = [
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.2, occurred_at=days_ago(20)),
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.3, occurred_at=days_ago(18)),
        indep(LEARNER_A, T_EUCLID, correct=True, score=0.95, occurred_at=days_ago(2)),
        indep(LEARNER_A, T_EUCLID, correct=True, score=1.0, occurred_at=days_ago(1)),
        score_event(subject=LEARNER_A, topic_id=T_EUCLID, raw_score=0.95, occurred_at=NOW),
    ]
    results = detect_gaps(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW)
    confirmed_conceptual = [r for r in results if r.confirmed and r.gap_type in ("conceptual", "procedural")]
    assert not confirmed_conceptual, "fresh strong reassessment should clear the concept gap"


def test_support_dependency_strong_only_when_supported():
    """Succeeds with help, fails alone -> support-dependency, confirmed."""
    events = [
        supported(LEARNER_A, T_EUCLID, correct=True, score=0.9, assistance_level="Coach", occurred_at=days_ago(4)),
        supported(LEARNER_A, T_EUCLID, correct=True, score=0.85, assistance_level="Coach", occurred_at=days_ago(3)),
        supported(LEARNER_A, T_EUCLID, correct=True, score=0.9, assistance_level="Hint", occurred_at=days_ago(2)),
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.2, occurred_at=days_ago(1)),
    ]
    gaps = _by_type(detect_gaps(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW))
    assert "support-dependency" in gaps
    assert gaps["support-dependency"].confirmed is True


def test_speed_distinguished_from_accuracy():
    """Correct-but-slow -> speed; right-method-with-slips -> accuracy. Separate."""
    slow = [
        indep(LEARNER_A, T_EUCLID, correct=True, score=1.0, time_taken_ms=200_000, occurred_at=days_ago(3)),
        indep(LEARNER_A, T_EUCLID, correct=True, score=1.0, time_taken_ms=180_000, occurred_at=days_ago(2)),
    ]
    speed_gaps = _by_type(detect_gaps(slow, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW))
    assert "speed" in speed_gaps and speed_gaps["speed"].confirmed
    assert "accuracy" not in speed_gaps  # fully correct -> not accuracy

    slips = [
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.7, time_taken_ms=20_000, occurred_at=days_ago(3)),
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.6, time_taken_ms=20_000, occurred_at=days_ago(2)),
    ]
    acc_gaps = _by_type(detect_gaps(slips, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW))
    assert "accuracy" in acc_gaps and acc_gaps["accuracy"].confirmed
    assert "speed" not in acc_gaps  # fast -> not speed


def test_prerequisite_gap_uses_confirmed_edge_only(seed_prereq_graph):
    """Weak on a topic whose CONFIRMED prerequisite is also weak -> prerequisite
    gap, routing back. T_IRRATIONAL <- T_FUNDTHM is a confirmed hard edge."""
    events = [
        # Weak on the prerequisite (Fundamental Theorem).
        indep(LEARNER_A, T_FUNDTHM, correct=False, score=0.2, occurred_at=days_ago(6)),
        indep(LEARNER_A, T_FUNDTHM, correct=False, score=0.25, occurred_at=days_ago(5)),
        # Weak on the dependent topic (Irrational proofs).
        indep(LEARNER_A, T_IRRATIONAL, correct=False, score=0.2, occurred_at=days_ago(3)),
        indep(LEARNER_A, T_IRRATIONAL, correct=False, score=0.3, occurred_at=days_ago(2)),
    ]
    gaps = _by_type(detect_gaps(
        events, subject=LEARNER_A, topic_id=T_IRRATIONAL, graph=seed_prereq_graph, asof=NOW,
    ))
    assert "prerequisite" in gaps
    assert gaps["prerequisite"].confirmed
    # Lineage spans both the dependent topic and the prerequisite evidence.
    assert len(gaps["prerequisite"].evidence.evidence_event_ids) >= 2


def test_unconfirmed_proposed_edge_does_not_drive_prerequisite_gap(seed_prereq_graph):
    """The proposed (unconfirmed) edge T_IRRATIONAL -> T_TRIG_RATIOS must NOT be
    used: weakness on trig ratios should not route back to irrationals."""
    from .conftest import T_TRIG_RATIOS

    events = [
        indep(LEARNER_A, T_IRRATIONAL, correct=False, score=0.2, occurred_at=days_ago(5)),
        indep(LEARNER_A, T_TRIG_RATIOS, correct=False, score=0.2, occurred_at=days_ago(3)),
        indep(LEARNER_A, T_TRIG_RATIOS, correct=False, score=0.25, occurred_at=days_ago(2)),
    ]
    gaps = _by_type(detect_gaps(
        events, subject=LEARNER_A, topic_id=T_TRIG_RATIOS, graph=seed_prereq_graph, asof=NOW,
    ))
    # No prerequisite gap, because the only edge into trig-ratios is unconfirmed.
    assert "prerequisite" not in gaps


def test_application_gap_easy_pass_hard_fail():
    events = [
        indep(LEARNER_A, T_EUCLID, correct=True, score=1.0, difficulty=0.2, occurred_at=days_ago(4)),
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.2, difficulty=0.8, occurred_at=days_ago(3)),
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.3, difficulty=0.9, occurred_at=days_ago(2)),
    ]
    gaps = _by_type(detect_gaps(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW))
    assert "application" in gaps
    assert gaps["application"].confirmed


def test_retention_gap_prior_success_then_stale():
    events = [
        indep(LEARNER_A, T_EUCLID, correct=True, score=0.95, occurred_at=days_ago(150)),
        indep(LEARNER_A, T_EUCLID, correct=True, score=0.9, occurred_at=days_ago(140)),
    ]
    gaps = _by_type(detect_gaps(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW))
    assert "retention" in gaps


def test_conceptual_when_failing_even_with_support():
    events = [
        supported(LEARNER_A, T_EUCLID, correct=False, score=0.1, assistance_level="Coach", occurred_at=days_ago(3)),
        supported(LEARNER_A, T_EUCLID, correct=False, score=0.05, assistance_level="Coach", occurred_at=days_ago(2)),
    ]
    gaps = _by_type(detect_gaps(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW))
    assert "conceptual" in gaps
    assert gaps["conceptual"].confirmed


def test_every_gap_carries_lineage_and_rationale():
    events = [
        supported(LEARNER_A, T_EUCLID, correct=False, score=0.1, assistance_level="Coach", occurred_at=days_ago(2)),
        supported(LEARNER_A, T_EUCLID, correct=False, score=0.15, assistance_level="Coach", occurred_at=days_ago(1)),
    ]
    for r in detect_gaps(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW):
        assert len(r.evidence.evidence_event_ids) >= 1
        assert r.evidence.rationale
        assert 0.0 <= r.evidence.confidence <= 1.0


def test_language_gap_is_proposed_never_confirmed():
    """Language is conservative: even a clear slow-wrong-easy pattern stays
    unconfirmed until a richer free-text/translation signal corroborates it."""
    events = [
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.2, difficulty=0.2, time_taken_ms=200_000, occurred_at=days_ago(3)),
        indep(LEARNER_A, T_EUCLID, correct=False, score=0.2, difficulty=0.3, time_taken_ms=210_000, occurred_at=days_ago(2)),
    ]
    gaps = _by_type(detect_gaps(events, subject=LEARNER_A, topic_id=T_EUCLID, asof=NOW))
    if "language" in gaps:
        assert gaps["language"].confirmed is False
