"""Coaching signals: PRIVATE, teacher-first, growth-framed, never a ranking."""

from __future__ import annotations

import pytest

from app.coaching import (
    CoachingSignal,
    EmploymentDecisionError,
    PunitiveRankingError,
    build_coaching_summary,
    employment_decision_guard,
    refuse_punitive_ranking,
)
from app.interaction import Utterance, analyse_interaction


TEACHER = "tttt0000-0000-4000-8000-000000000001"
L1 = "ll110000-0000-4000-8000-000000000001"
L2 = "ll220000-0000-4000-8000-000000000002"
L3 = "ll330000-0000-4000-8000-000000000003"
L4 = "ll440000-0000-4000-8000-000000000004"
TEACHER_CONSENT = "cccc0000-0000-4000-8000-000000000007"


def _teacher_heavy_metrics():
    # Mostly teacher talk, recall-only questions, dominated voices, no wait time.
    return analyse_interaction(
        lesson_id="lesson_a",
        teacher_ref=TEACHER,
        utterances=[
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=180,
                      is_question=True, question_level="lower_order",
                      responded_after_s=1.0),
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=0,
                      is_question=True, question_level="lower_order",
                      responded_after_s=1.0),
            Utterance(speaker_ref=L1, role="learner", duration_s=30),
            Utterance(speaker_ref=L2, role="learner", duration_s=2),
        ],
    )


def _strong_metrics():
    return analyse_interaction(
        lesson_id="lesson_b",
        teacher_ref=TEACHER,
        utterances=[
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=40,
                      is_question=True, question_level="higher_order",
                      responded_after_s=4.0),
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=10,
                      is_question=True, question_level="higher_order",
                      responded_after_s=3.5),
            Utterance(speaker_ref=L1, role="learner", duration_s=25),
            Utterance(speaker_ref=L2, role="learner", duration_s=25),
            Utterance(speaker_ref=L3, role="learner", duration_s=25),
            Utterance(speaker_ref=L4, role="learner", duration_s=25),
        ],
    )


def test_every_signal_is_private_and_teacher_first():
    summary = build_coaching_summary(_strong_metrics())
    assert summary.private is True
    assert summary.visibility == "teacher_first"
    for sig in summary.signals:
        assert sig.private is True
        assert sig.visibility == "teacher_first"
        # Default audience is the teacher alone.
        assert sig.audience() == ["teacher"]


def test_signal_cannot_be_constructed_public():
    with pytest.raises(ValueError):
        CoachingSignal(
            teacher_ref=TEACHER, lesson_id="l", dimension="talk_ratio",
            direction="strength", reading="r", suggested_next_step="s",
            evidence="e", confidence="high", private=False,
        )
    with pytest.raises(ValueError):
        CoachingSignal(
            teacher_ref=TEACHER, lesson_id="l", dimension="talk_ratio",
            direction="strength", reading="r", suggested_next_step="s",
            evidence="e", confidence="high", visibility="public",
        )


def test_audience_widens_only_with_teacher_consent():
    summary = build_coaching_summary(_strong_metrics())
    sig = summary.signals[0]
    # Without consent: teacher only. With the teacher's own consent: shared.
    assert sig.audience() == ["teacher"]
    assert "shared_with_consent" in sig.audience(
        shared_by_teacher_consent_ref=TEACHER_CONSENT
    )


def test_summary_produces_one_signal_per_dimension():
    summary = build_coaching_summary(_strong_metrics())
    dims = {s.dimension for s in summary.signals}
    assert dims == {"talk_ratio", "questioning_quality", "equity_of_voice", "wait_time"}


def test_strong_lesson_reads_as_strengths():
    summary = build_coaching_summary(_strong_metrics())
    # Balanced talk, open questions, even voices, real wait time -> strengths.
    assert summary.strengths
    assert any(s.dimension == "talk_ratio" for s in summary.strengths)
    assert any(s.dimension == "wait_time" for s in summary.strengths)


def test_teacher_heavy_lesson_surfaces_growth_areas_not_punishment():
    summary = build_coaching_summary(_teacher_heavy_metrics())
    assert summary.growth_areas
    # Growth-framed: each carries one concrete, optional next step + evidence.
    for sig in summary.growth_areas:
        assert sig.suggested_next_step
        assert sig.evidence
    # And it is still private — a deficit reading is never made public.
    assert summary.private is True


def test_signals_are_deterministic():
    m = _teacher_heavy_metrics()
    a = build_coaching_summary(m)
    b = build_coaching_summary(m)
    assert [(s.dimension, s.direction, s.confidence) for s in a.signals] == \
           [(s.dimension, s.direction, s.confidence) for s in b.signals]


def test_no_punitive_ranking_is_producible():
    # The prohibition is a callable contract: it always refuses.
    with pytest.raises(PunitiveRankingError):
        refuse_punitive_ranking(["teacher_a", "teacher_b"])
    # There is no function on the summary that ranks teachers.
    summary = build_coaching_summary(_strong_metrics())
    assert not hasattr(summary, "rank")
    assert not hasattr(summary, "rating")
    assert not hasattr(summary, "score")


def test_employment_decision_is_guarded():
    with pytest.raises(EmploymentDecisionError):
        employment_decision_guard(teacher=TEACHER, action="renew")


def test_why_am_i_seeing_this_explains_privacy():
    sig = build_coaching_summary(_strong_metrics()).signals[0]
    why = sig.why_am_i_seeing_this
    assert "private" in why.lower()
    assert "not a rating" in why.lower()
