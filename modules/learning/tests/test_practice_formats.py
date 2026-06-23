"""Practice formats, topic quizzes, and the per-student aptitude score (d12)."""

from __future__ import annotations

import pytest

from learning import practice
from learning.practice import (
    ALL_PRACTICE_FORMATS,
    AptitudeObservation,
    PracticeFormat,
    QuizItemResult,
    TopicState,
    grade_topic_quiz,
    recommend_format,
    track_aptitude,
)


def _state(topic="a", band="developing", indep=0.4, *, obs=5, struggle=False, confirmed=()):
    return TopicState(
        topic_id=topic, band=band, independence=indep, performance=0.5,
        observation_count=obs, last_rung_used="Coach", recent_struggle=struggle,
        confirmed_gap_types=confirmed,
    )


# --- formats ---------------------------------------------------------------
def test_all_formats_have_specs():
    for f in ALL_PRACTICE_FORMATS:
        assert f in practice.FORMAT_SPECS


def test_speed_gap_recommends_timed_fluency():
    spec = recommend_format(_state(confirmed=("speed",)))
    assert spec.fmt is PracticeFormat.TIMED_FLUENCY
    assert spec.timed is True


def test_retention_gap_recommends_spaced_retrieval():
    spec = recommend_format(_state(confirmed=("retention",)))
    assert spec.fmt is PracticeFormat.SPACED_RETRIEVAL


def test_independent_no_gap_gets_a_challenge():
    spec = recommend_format(_state(band="independent", indep=0.9, confirmed=()))
    assert spec.fmt is PracticeFormat.CHALLENGE


def test_seasoned_topic_no_gap_gets_a_topic_quiz():
    spec = recommend_format(_state(band="secure", obs=6, confirmed=()))
    assert spec.fmt is PracticeFormat.TOPIC_QUIZ


def test_fresh_topic_gets_single_item():
    spec = recommend_format(_state(band="emerging", obs=1, confirmed=()))
    assert spec.fmt is PracticeFormat.SINGLE_ITEM


# --- topic quiz: rewards comprehension -------------------------------------
def test_quiz_rewards_independent_hard_items_over_easy_supported():
    hard_indep = grade_topic_quiz("t", [
        QuizItemResult(correct=True, independent=True, difficulty=0.9),
        QuizItemResult(correct=True, independent=True, difficulty=0.8),
    ])
    easy_supported = grade_topic_quiz("t", [
        QuizItemResult(correct=True, independent=False, difficulty=0.2),
        QuizItemResult(correct=True, independent=False, difficulty=0.2),
    ])
    # Both are "all correct", but comprehension is higher for hard independent work.
    assert hard_indep.comprehension_score > easy_supported.comprehension_score
    assert hard_indep.raw_correct == easy_supported.raw_correct == 2


def test_quiz_not_a_flat_percentage():
    res = grade_topic_quiz("t", [
        QuizItemResult(correct=True, independent=False, difficulty=0.2),
        QuizItemResult(correct=False, independent=True, difficulty=0.9),
    ])
    # Raw is 1/2 = 0.5; comprehension differs because of weighting.
    assert res.comprehension_score != 0.5


def test_quiz_plain_language_present_and_clean():
    res = grade_topic_quiz("t", [QuizItemResult(correct=True, independent=True, difficulty=0.7)])
    assert res.plain_language and "%" not in res.plain_language


def test_quiz_requires_items():
    with pytest.raises(ValueError):
        grade_topic_quiz("t", [])


# --- aptitude / readiness score --------------------------------------------
def _ob(correct=True, indep=True, diff=0.5, score=None):
    return AptitudeObservation(correct=correct, independent=indep, difficulty=diff, score=score)


def test_aptitude_too_early_with_no_practice():
    r = track_aptitude([])
    assert r.trend == "too-early" and r.sample_size == 0


def test_aptitude_rises_with_recent_improvement():
    obs = [_ob(False, False, 0.5), _ob(False, True, 0.5), _ob(True, True, 0.6), _ob(True, True, 0.7)]
    r = track_aptitude(obs)
    assert r.trend == "rising"


def test_aptitude_slips_with_recent_decline():
    obs = [_ob(True, True, 0.6), _ob(True, True, 0.6), _ob(False, True, 0.6), _ob(False, False, 0.6)]
    r = track_aptitude(obs)
    assert r.trend == "slipping"


def test_aptitude_independence_lifts_score():
    indep = track_aptitude([_ob(True, True, 0.7) for _ in range(6)])
    supp = track_aptitude([_ob(True, False, 0.7) for _ in range(6)])
    assert indep.score > supp.score


def test_aptitude_is_deterministic():
    obs = [_ob(True, True, 0.6), _ob(False, True, 0.5), _ob(True, True, 0.7)]
    assert track_aptitude(obs) == track_aptitude(obs)


def test_aptitude_plain_language_no_percentage():
    r = track_aptitude([_ob() for _ in range(5)])
    assert "%" not in r.plain_language
