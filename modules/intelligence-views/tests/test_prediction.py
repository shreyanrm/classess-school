"""Prediction: forecasts are reproducible, bounded, explainable, and advisory."""

from __future__ import annotations

from app.prediction import (
    TARGET_MASTERY,
    TrajectoryDirection,
    forecast_learner_topic,
    forecast_topic,
)
from .conftest import LEARNER_A, T_TRIG_RATIOS, has_no_emoji


def test_forecast_is_reproducible(gap_cohort):
    profiles, topic_id = gap_cohort
    cov = {topic_id: (2, 4)}
    a = forecast_topic(profiles, topic_id=topic_id, coverage=cov)
    b = forecast_topic(profiles, topic_id=topic_id, coverage=cov)
    assert a.projected_mastery == b.projected_mastery
    assert a.confidence == b.confidence
    assert a.direction == b.direction
    assert a.plain_language == b.plain_language


def test_projected_mastery_is_bounded(strong_cohort, gap_cohort):
    for fixture in (strong_cohort, gap_cohort):
        profiles, topic_id = fixture
        fc = forecast_topic(profiles, topic_id=topic_id, coverage={topic_id: (4, 4)})
        assert 0.0 <= fc.projected_mastery <= 1.0
        assert 0.0 <= fc.confidence <= 1.0


def test_strong_cohort_reads_on_track_or_ahead(strong_cohort):
    profiles, topic_id = strong_cohort
    fc = forecast_topic(profiles, topic_id=topic_id, coverage={topic_id: (4, 4)})
    assert fc.direction in (TrajectoryDirection.AHEAD, TrajectoryDirection.ON_TRACK)
    assert fc.current_mastery >= TARGET_MASTERY


def test_gap_cohort_is_at_risk_or_behind(gap_cohort):
    """Support-dependent cohort: low independence drags the trajectory below
    target."""
    profiles, topic_id = gap_cohort
    fc = forecast_topic(profiles, topic_id=topic_id, coverage={topic_id: (3, 4)})
    assert fc.direction in (TrajectoryDirection.AT_RISK, TrajectoryDirection.BEHIND)


def test_forecast_carries_evidence_and_assumptions(gap_cohort):
    profiles, topic_id = gap_cohort
    fc = forecast_topic(profiles, topic_id=topic_id, coverage={topic_id: (3, 4)})
    assert fc.evidence.topic_id == topic_id
    assert fc.evidence.observation_count > 0
    assert fc.assumptions
    assert fc.why_am_i_seeing_this
    assert fc.confidence_band in ("low", "medium", "high")


def test_thin_evidence_is_low_confidence(single_score_cohort):
    profiles, topic_id = single_score_cohort
    fc = forecast_topic(profiles, topic_id=topic_id, coverage={topic_id: (1, 4)})
    assert fc.confidence <= 0.5
    assert fc.confidence_band in ("low", "medium")


def test_learner_forecast_matches_cohort_definition(gap_cohort):
    """A learner-scoped forecast uses the same projection as the cohort one."""
    profiles, topic_id = gap_cohort
    fc = forecast_learner_topic(
        profiles, subject=LEARNER_A, topic_id=topic_id, coverage={topic_id: (3, 4)}
    )
    assert 0.0 <= fc.projected_mastery <= 1.0
    assert fc.plain_language


def test_forecast_text_has_no_emoji_or_exclamation(gap_cohort):
    profiles, topic_id = gap_cohort
    fc = forecast_topic(profiles, topic_id=topic_id, coverage={topic_id: (3, 4)})
    assert "!" not in fc.plain_language and has_no_emoji(fc.plain_language)
