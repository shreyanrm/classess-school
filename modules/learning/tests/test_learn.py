"""Pose -> struggle -> reveal flow: reveal is refused before a genuine attempt,
and the independent-vs-supported flag is set from whether help was used."""

from __future__ import annotations

import pytest

from learning import learn
from learning.learn import LearnSession, StruggleNotGenuineError


def test_reveal_refused_before_genuine_attempt():
    s = LearnSession.pose(topic_id="t1", offered_rung="Hint", min_struggle_ms=15_000)
    assert s.phase == "posed"
    assert not s.attempt_is_genuine
    with pytest.raises(StruggleNotGenuineError):
        s.reveal()


def test_min_struggle_never_zero():
    # A zero/negative gate is rejected and replaced with the default — no
    # explain-first shortcut is ever permitted.
    s = LearnSession.pose(topic_id="t1", min_struggle_ms=0)
    assert s.min_struggle_ms == learn.DEFAULT_MIN_STRUGGLE_MS


def test_genuine_by_time_then_reveal_makes_it_supported():
    s = LearnSession.pose(topic_id="t1", offered_rung="Coach", difficulty=0.5)
    s.record_engagement(elapsed_ms=20_000)
    assert s.attempt_is_genuine
    rung = s.reveal()
    assert rung == "Coach"
    assert s.used_help
    payload = s.resolve(correct=True, score=0.7)
    assert payload["mode"] == "supported"
    assert payload["assistance_level"] == "Coach"


def test_genuine_by_submitted_try_unaided_is_independent():
    s = LearnSession.pose(topic_id="t1")
    # A submitted try with a short time still counts as a genuine attempt.
    s.record_engagement(elapsed_ms=2_000, submitted_try=True)
    assert s.attempt_is_genuine
    # No reveal used -> the attempt is an unaided demonstration.
    payload = s.resolve(correct=True)
    assert payload["mode"] == "independent"
    assert payload["assistance_level"] == "Independent"


def test_reveal_at_independent_rung_is_coerced_to_help():
    # 'Independent' is not a help rung; revealing at it must not produce an
    # incoherent independent-but-helped attempt.
    s = LearnSession.pose(topic_id="t1", offered_rung="Independent")
    s.record_engagement(elapsed_ms=20_000)
    used = s.reveal()
    assert used != "Independent"
    payload = s.resolve(correct=False, score=0.2)
    assert payload["mode"] == "supported"


def test_summary_is_pii_free_and_plain():
    s = LearnSession.pose(topic_id="t1")
    s.record_engagement(elapsed_ms=16_000)
    s.reveal()
    summ = s.summary()
    assert summ["help_used"] is True
    assert summ["independent"] is False
    # No raw mastery number, no name anywhere.
    assert "topic_id" in summ and "score" not in summ
