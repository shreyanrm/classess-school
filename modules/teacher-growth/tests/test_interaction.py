"""Classroom-interaction metrics: deterministic, descriptive, opaque-ref only."""

from __future__ import annotations

import pytest

from app.interaction import Utterance, analyse_interaction


TEACHER = "tttt0000-0000-4000-8000-000000000001"
L1 = "ll110000-0000-4000-8000-000000000001"
L2 = "ll220000-0000-4000-8000-000000000002"
L3 = "ll330000-0000-4000-8000-000000000003"
L4 = "ll440000-0000-4000-8000-000000000004"


def test_talk_ratio_is_share_of_speaking_time():
    metrics = analyse_interaction(
        lesson_id="lesson1",
        teacher_ref=TEACHER,
        utterances=[
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=60),
            Utterance(speaker_ref=L1, role="learner", duration_s=20),
            Utterance(speaker_ref=L2, role="learner", duration_s=20),
        ],
    )
    # 60 of 100s teacher -> 0.6 teacher talk ratio.
    assert metrics.teacher_talk_ratio == 0.6
    assert metrics.learner_talk_ratio == 0.4
    assert metrics.total_talk_s == 100.0


def test_talk_ratio_is_zero_when_silent_not_misleading():
    metrics = analyse_interaction(lesson_id="silent", teacher_ref=TEACHER, utterances=[])
    # No signal rather than a misleading 100% teacher.
    assert metrics.teacher_talk_ratio == 0.0
    assert metrics.learner_talk_ratio == 0.0


def test_questioning_quality_counts_levels():
    metrics = analyse_interaction(
        lesson_id="q",
        teacher_ref=TEACHER,
        utterances=[
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=5,
                      is_question=True, question_level="higher_order"),
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=3,
                      is_question=True, question_level="lower_order"),
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=3,
                      is_question=True, question_level="lower_order"),
        ],
    )
    assert metrics.total_questions == 3
    assert metrics.higher_order_questions == 1
    assert metrics.lower_order_questions == 2
    assert metrics.higher_order_fraction == round(1 / 3, 4)


def test_equity_of_voice_high_when_even():
    metrics = analyse_interaction(
        lesson_id="even",
        teacher_ref=TEACHER,
        utterances=[
            Utterance(speaker_ref=L1, role="learner", duration_s=10),
            Utterance(speaker_ref=L2, role="learner", duration_s=10),
            Utterance(speaker_ref=L3, role="learner", duration_s=10),
            Utterance(speaker_ref=L4, role="learner", duration_s=10),
        ],
    )
    assert metrics.voices_count == 4
    # Perfectly even participation -> evenness 1.0.
    assert metrics.equity_of_voice == 1.0


def test_equity_of_voice_low_when_dominated():
    metrics = analyse_interaction(
        lesson_id="skewed",
        teacher_ref=TEACHER,
        utterances=[
            Utterance(speaker_ref=L1, role="learner", duration_s=90),
            Utterance(speaker_ref=L2, role="learner", duration_s=5),
            Utterance(speaker_ref=L3, role="learner", duration_s=5),
        ],
    )
    # One voice dominates -> evenness well below 1.0.
    assert metrics.equity_of_voice < 0.6


def test_wait_time_averages_response_gaps():
    metrics = analyse_interaction(
        lesson_id="wait",
        teacher_ref=TEACHER,
        utterances=[
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=4,
                      is_question=True, question_level="higher_order",
                      responded_after_s=4.0),
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=4,
                      is_question=True, question_level="lower_order",
                      responded_after_s=2.0),
        ],
    )
    assert metrics.average_wait_time_s == 3.0
    assert len(metrics.wait_time_samples) == 2


def test_metrics_are_deterministic_for_same_input():
    utterances = [
        Utterance(speaker_ref=TEACHER, role="teacher", duration_s=30,
                  is_question=True, question_level="higher_order",
                  responded_after_s=3.5),
        Utterance(speaker_ref=L1, role="learner", duration_s=10),
        Utterance(speaker_ref=L2, role="learner", duration_s=15),
    ]
    a = analyse_interaction(lesson_id="x", teacher_ref=TEACHER, utterances=list(utterances))
    b = analyse_interaction(lesson_id="x", teacher_ref=TEACHER, utterances=list(utterances))
    # Identical input -> identical metrics (deterministic guarantee).
    assert a.teacher_talk_ratio == b.teacher_talk_ratio
    assert a.equity_of_voice == b.equity_of_voice
    assert a.average_wait_time_s == b.average_wait_time_s
    assert a.higher_order_fraction == b.higher_order_fraction


def test_only_teacher_can_be_a_tracked_question():
    with pytest.raises(ValueError):
        Utterance(speaker_ref=L1, role="learner", duration_s=3, is_question=True)


def test_negative_duration_rejected():
    with pytest.raises(ValueError):
        Utterance(speaker_ref=TEACHER, role="teacher", duration_s=-1)


def test_evidence_strings_explain_each_metric():
    metrics = analyse_interaction(
        lesson_id="ev",
        teacher_ref=TEACHER,
        utterances=[
            Utterance(speaker_ref=TEACHER, role="teacher", duration_s=60,
                      is_question=True, question_level="higher_order",
                      responded_after_s=3.0),
            Utterance(speaker_ref=L1, role="learner", duration_s=40),
        ],
    )
    ev = metrics.evidence()
    assert set(ev) == {"talk_ratio", "questioning_quality", "equity_of_voice", "wait_time"}
    assert all(isinstance(v, str) and v for v in ev.values())
