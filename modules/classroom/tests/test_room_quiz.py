"""Device-free room-photo quiz: detection gating, scoring, live leaderboard."""

from __future__ import annotations

import pytest

from app import events
from app.device_free_check import ScanCard
from app.room_quiz import (
    CaptureOutcome,
    CardDetection,
    RoomQuiz,
)


def _uuid() -> str:
    return events.new_canonical_uuid()


_CODES = [
    "CLSS-AA11-AA11-AA11",
    "CLSS-BB22-BB22-BB22",
    "CLSS-CC33-CC33-CC33",
]


def _quiz_with_cards(n=3):
    quiz = RoomQuiz("s1", lesson_ref="lesson://photosynthesis")
    subs = []
    for i in range(n):
        u = _uuid()
        subs.append(u)
        quiz.register_card(ScanCard(code=_CODES[i], subject_uuid=u))
    quiz.set_answer_key("q1", "b")
    return quiz, subs


def test_detection_requires_valid_code_and_confidence_bounds():
    with pytest.raises(ValueError):
        CardDetection(card_code="nope", side="a", confidence=0.9)
    with pytest.raises(ValueError):
        CardDetection(card_code=_CODES[0], side="a", confidence=2.0)


def test_resolved_detection_scored_against_key():
    quiz, subs = _quiz_with_cards()
    res = quiz.capture("q1", CardDetection(_CODES[0], "b", 0.9))
    assert res.outcome is CaptureOutcome.RESOLVED
    assert res.correct is True
    assert res.subject_uuid == subs[0]


def test_below_gate_detection_is_unresolved_not_guessed():
    quiz, _ = _quiz_with_cards()
    res = quiz.capture("q1", CardDetection(_CODES[0], "b", 0.4))
    assert res.outcome is CaptureOutcome.UNRESOLVED
    assert res.side is None
    # nothing recorded -> no leaderboard entry
    assert quiz.leaderboard() == []


def test_unknown_card_is_held_back():
    quiz, _ = _quiz_with_cards()
    res = quiz.capture("q1", CardDetection("CLSS-ZZ99-ZZ99-ZZ99", "b", 0.99))
    assert res.outcome is CaptureOutcome.UNKNOWN_CARD
    assert res.subject_uuid is None


def test_unknown_question_rejected():
    quiz, _ = _quiz_with_cards()
    with pytest.raises(ValueError):
        quiz.capture("q-missing", CardDetection(_CODES[0], "b", 0.9))


def test_idempotent_per_subject_question():
    quiz, subs = _quiz_with_cards()
    quiz.capture("q1", CardDetection(_CODES[0], "a", 0.7))  # wrong
    quiz.capture("q1", CardDetection(_CODES[0], "b", 0.95))  # clearer, correct
    assert quiz.score_for(subs[0]) == 1
    rows = quiz.leaderboard()
    # one subject answered, score 1
    me = [r for r in rows if r.subject_uuid == subs[0]][0]
    assert me.score == 1
    assert me.answered == 1


def test_leaderboard_ranks_scores_descending_no_pii():
    quiz, subs = _quiz_with_cards()
    quiz.set_answer_key("q2", "a")
    # subject 0 gets both right; subject 1 gets one; subject 2 gets none
    quiz.capture_photo("q1", [
        CardDetection(_CODES[0], "b", 0.9),
        CardDetection(_CODES[1], "b", 0.9),
        CardDetection(_CODES[2], "a", 0.9),
    ])
    quiz.capture_photo("q2", [
        CardDetection(_CODES[0], "a", 0.9),
        CardDetection(_CODES[1], "c", 0.9),
        CardDetection(_CODES[2], "c", 0.9),
    ])
    rows = quiz.leaderboard()
    assert [r.score for r in rows] == [2, 1, 0]
    # leaderboard carries opaque uuids only, no names
    assert all(events.is_opaque_uuid(r.subject_uuid) for r in rows)


def test_capture_event_is_grasp_evidence_not_punitive():
    quiz, subs = _quiz_with_cards()
    res = quiz.capture("q1", CardDetection(_CODES[0], "a", 0.9))  # wrong
    ev = quiz.capture_event(res)
    assert ev.kind is events.EventKind.ROOM_PHOTO_CAPTURE
    assert ev.payload["correct"] is False
    assert ev.payload["punitive"] is False
    assert ev.payload["assistive"] is True
    assert ev.payload["lesson_ref"] == "lesson://photosynthesis"


def test_no_event_for_unresolved_capture():
    quiz, _ = _quiz_with_cards()
    res = quiz.capture("q1", CardDetection(_CODES[0], "b", 0.3))
    assert quiz.capture_event(res) is None
