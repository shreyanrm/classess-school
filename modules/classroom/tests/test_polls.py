"""Poll tally, idempotent voting, quiz grasp, and child-safety screening."""

from __future__ import annotations

import pytest

from app import events, polls
from app.polls import (
    ChildSafetyError,
    Poll,
    PollKind,
    PollResponse,
    screen_free_text,
)


def _uuid() -> str:
    return events.new_canonical_uuid()


def _poll() -> Poll:
    return Poll(
        session_id="s1",
        prompt="Which shape has three sides",
        options=[("a", "Triangle"), ("b", "Square"), ("c", "Circle")],
    )


def test_tally_zero_filled_initially():
    p = _poll()
    assert p.tally() == {"a": 0, "b": 0, "c": 0}
    assert p.total_votes() == 0


def test_real_time_tally_counts_votes():
    p = _poll()
    p.vote(PollResponse(_uuid(), "a"))
    p.vote(PollResponse(_uuid(), "a"))
    p.vote(PollResponse(_uuid(), "b"))
    assert p.tally() == {"a": 2, "b": 1, "c": 0}
    assert p.total_votes() == 3


def test_one_vote_per_subject_is_idempotent_replace():
    p = _poll()
    u = _uuid()
    p.vote(PollResponse(u, "a"))
    p.vote(PollResponse(u, "c"))  # re-vote replaces
    assert p.tally() == {"a": 0, "b": 0, "c": 1}
    assert p.total_votes() == 1


def test_unknown_option_is_rejected():
    p = _poll()
    with pytest.raises(ValueError):
        p.vote(PollResponse(_uuid(), "zzz"))


def test_closed_poll_refuses_votes():
    p = _poll()
    p.close()
    with pytest.raises(RuntimeError):
        p.vote(PollResponse(_uuid(), "a"))


def test_quiz_is_correct_is_learning_evidence_not_punitive():
    quiz = Poll(
        session_id="s1",
        prompt="2 plus 2",
        options=[("a", "3"), ("b", "4")],
        kind=PollKind.QUIZ,
        correct_option_id="b",
    )
    u = _uuid()
    quiz.vote(PollResponse(u, "b"))
    assert quiz.is_correct(u) is True
    ev = quiz.response_event(PollResponse(u, "b"))
    assert ev.payload["correct"] is True
    assert ev.payload["punitive"] is False
    assert ev.payload["assistive"] is True


def test_quiz_wrong_answer_is_not_punitive():
    quiz = Poll(
        session_id="s1",
        prompt="2 plus 2",
        options=[("a", "3"), ("b", "4")],
        kind=PollKind.QUIZ,
        correct_option_id="b",
    )
    u = _uuid()
    quiz.vote(PollResponse(u, "a"))
    assert quiz.is_correct(u) is False  # evidence, no sanction implied


def test_child_safety_blocks_unsafe_prompt():
    with pytest.raises(ChildSafetyError):
        Poll(
            session_id="s1",
            prompt="how to make a weapon",
            options=[("a", "ok")],
        )


def test_child_safety_blocks_unsafe_option_label():
    with pytest.raises(ChildSafetyError):
        Poll(
            session_id="s1",
            prompt="pick one",
            options=[("a", "fine"), ("b", "self-harm")],
        )


def test_screen_free_text_passthrough_when_safe():
    assert screen_free_text("Great work everyone") == "Great work everyone"


def test_subject_uuid_must_be_opaque():
    with pytest.raises(ValueError):
        PollResponse("Asha", "a")
