"""Study quadrant: effort x outcome placement is deterministic, plain-language,
and resolves both axes through the shared semantic layer."""

from __future__ import annotations

from app.study_quadrant import (
    Quadrant,
    place_cohort,
    place_learner,
    quadrant_summary,
)
from .conftest import LEARNER_A, LEARNER_B, T_TRIG_RATIOS, has_no_emoji


def test_strong_cohort_high_effort_thrives(strong_cohort):
    profiles, topic_id = strong_cohort
    effort = {LEARNER_A: 0.9, LEARNER_B: 0.9}
    p = place_cohort(profiles, topic_id=topic_id, effort=effort)
    assert p.quadrant == Quadrant.THRIVING


def test_high_effort_low_outcome_needs_support(gap_cohort):
    """The support-dependent cohort works hard but does not land independently —
    the most important quadrant."""
    profiles, topic_id = gap_cohort
    effort = {LEARNER_A: 0.9, LEARNER_B: 0.9}
    p = place_cohort(profiles, topic_id=topic_id, effort=effort)
    assert p.quadrant == Quadrant.NEEDS_SUPPORT


def test_low_effort_low_outcome_needs_reengage(gap_cohort):
    profiles, topic_id = gap_cohort
    effort = {LEARNER_A: 0.1, LEARNER_B: 0.1}
    p = place_cohort(profiles, topic_id=topic_id, effort=effort)
    assert p.quadrant == Quadrant.NEEDS_REENGAGE


def test_placement_is_explainable_and_plain(gap_cohort):
    profiles, topic_id = gap_cohort
    p = place_cohort(profiles, topic_id=topic_id, effort={LEARNER_A: 0.9, LEARNER_B: 0.9})
    assert p.plain_language
    assert p.why_am_i_seeing_this
    assert p.effort_words and p.outcome_words
    assert "!" not in p.plain_language and has_no_emoji(p.plain_language)


def test_placement_is_deterministic(gap_cohort):
    profiles, topic_id = gap_cohort
    effort = {LEARNER_A: 0.9, LEARNER_B: 0.9}
    a = place_cohort(profiles, topic_id=topic_id, effort=effort)
    b = place_cohort(profiles, topic_id=topic_id, effort=effort)
    assert a.axes == b.axes
    assert a.quadrant == b.quadrant


def test_learner_placement_scoped_to_learner(gap_cohort):
    profiles, topic_id = gap_cohort
    p = place_learner(profiles, subject=LEARNER_A, topic_id=topic_id, effort={LEARNER_A: 0.9})
    assert p.quadrant in set(Quadrant)
    assert p.label == "This learner"


def test_quadrant_summary_counts(gap_cohort, strong_cohort):
    gp, gt = gap_cohort
    sp, st = strong_cohort
    placements = [
        place_cohort(gp, topic_id=gt, effort={LEARNER_A: 0.9, LEARNER_B: 0.9}),
        place_cohort(sp, topic_id=st, effort={LEARNER_A: 0.9, LEARNER_B: 0.9}),
    ]
    summary = quadrant_summary(placements)
    assert summary[Quadrant.NEEDS_SUPPORT.value] == 1
    assert summary[Quadrant.THRIVING.value] == 1
    assert sum(summary.values()) == 2
