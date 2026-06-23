"""Roster-wide engagement<->later-performance summary for a topic.

Counts and cohort averages only -- never a per-learner ranking, never a verdict
on a person; uncertain learners are excluded from the relation, not guessed."""

from __future__ import annotations

import pytest

from app import events
from app.attention import (
    EngagementBand,
    TopicEngagementSummary,
    relate_engagement_to_performance,
    summarise_topic_engagement,
)


def _uuid() -> str:
    return events.new_canonical_uuid()


def _link(band: EngagementBand, score: float):
    return relate_engagement_to_performance(_uuid(), "topic://photosynthesis", band, score)


def test_summary_requires_topic_ref():
    with pytest.raises(ValueError):
        summarise_topic_engagement("", [])


def test_cohort_engaged_and_performed_well():
    links = [
        _link(EngagementBand.ENGAGED, 0.9),
        _link(EngagementBand.ENGAGED, 0.8),
        _link(EngagementBand.SETTLING, 0.7),
    ]
    s = summarise_topic_engagement("topic://photosynthesis", links)
    assert s.learners == 3
    assert s.uncertain == 0
    assert s.avg_later_score == pytest.approx(0.8, abs=0.01)
    assert "performed well" in s.cohort_relation


def test_cohort_low_engagement_low_scores_flags_revisit():
    links = [
        _link(EngagementBand.NEEDS_A_NUDGE, 0.2),
        _link(EngagementBand.NEEDS_A_NUDGE, 0.3),
    ]
    s = summarise_topic_engagement("topic://photosynthesis", links)
    assert "revisit" in s.cohort_relation


def test_uncertain_learners_excluded_from_relation_but_counted():
    links = [
        _link(EngagementBand.UNCERTAIN, 0.0),
        _link(EngagementBand.ENGAGED, 0.9),
    ]
    s = summarise_topic_engagement("topic://photosynthesis", links)
    assert s.learners == 2
    assert s.uncertain == 1
    # avg score computed over the confident learner only
    assert s.avg_later_score == pytest.approx(0.9, abs=0.01)


def test_all_uncertain_gives_no_reliable_read():
    links = [_link(EngagementBand.UNCERTAIN, 0.0), _link(EngagementBand.UNCERTAIN, 0.0)]
    s = summarise_topic_engagement("topic://photosynthesis", links)
    assert s.avg_later_score == 0.0
    assert "uncertain" in s.cohort_relation.lower()


def test_summary_carries_no_per_learner_ranking():
    # The summary type exposes counts/averages only -- no list of subject uuids.
    s = summarise_topic_engagement("topic://x", [_link(EngagementBand.ENGAGED, 0.9)])
    assert s.assistive is True
    fields = set(vars(s))
    assert "subject_uuid" not in fields
    assert not any("rank" in f for f in fields)
