"""Pacing protection feed: advisory signals routed to scheduling."""

from planning.app.events import EventLog, EventType
from planning.app.pacing_link import (
    PacingProtectionFeed,
    PacingSignal,
    PacingState,
    RecommendedAction,
)

SUBJECT = "class-uuid"


def test_behind_when_deficit_exceeds_threshold():
    feed = PacingProtectionFeed(behind_threshold_minutes=20)
    sig = feed.assess(SUBJECT, planned_minutes=100, delivered_minutes=70, rolled_over_count=0)
    assert sig.state == PacingState.BEHIND
    assert sig.deficit_minutes == 30
    assert sig.recommended_action == RecommendedAction.RECLAIM_BUFFER


def test_rollover_marks_behind_even_with_small_deficit():
    feed = PacingProtectionFeed(behind_threshold_minutes=20)
    sig = feed.assess(SUBJECT, planned_minutes=40, delivered_minutes=40, rolled_over_count=2)
    assert sig.state == PacingState.BEHIND
    assert sig.recommended_action == RecommendedAction.PROTECT_BLOCK


def test_ahead_when_delivered_exceeds_planned():
    feed = PacingProtectionFeed(ahead_threshold_minutes=20)
    sig = feed.assess(SUBJECT, planned_minutes=40, delivered_minutes=70, rolled_over_count=0)
    assert sig.state == PacingState.AHEAD
    assert sig.recommended_action == RecommendedAction.RELEASE_BUFFER


def test_on_track_within_thresholds():
    feed = PacingProtectionFeed()
    sig = feed.assess(SUBJECT, planned_minutes=40, delivered_minutes=40, rolled_over_count=0)
    assert sig.state == PacingState.ON_TRACK
    assert sig.recommended_action == RecommendedAction.NONE


def test_signal_routed_to_injected_scheduler_adapter():
    received = []
    feed = PacingProtectionFeed(deliver=received.append)
    sig, ok = feed.assess_and_feed(SUBJECT, 100, 60, 1)
    assert ok is True
    assert received and received[0] is sig


def test_degrades_gracefully_without_scheduler():
    feed = PacingProtectionFeed()  # no deliver adapter
    sig, ok = feed.assess_and_feed(SUBJECT, 100, 60, 1)
    assert ok is True
    assert feed.buffered == (sig,)


def test_low_confidence_signal_is_held_for_human_review():
    received = []
    feed = PacingProtectionFeed(deliver=received.append, confidence_gate=0.5)
    sig = feed.assess(SUBJECT, 100, 60, 0, confidence=0.2)
    delivered = feed.feed(sig)
    assert delivered is False
    assert received == []  # never auto-fired to scheduler
    assert feed.held == (sig,)


def test_pacing_signal_requires_canonical_subject():
    import pytest

    with pytest.raises(ValueError):
        PacingSignal(
            subject_uuid="",
            state=PacingState.ON_TRACK,
            deficit_minutes=0,
            rolled_over_count=0,
            recommended_action=RecommendedAction.NONE,
        )


def test_feed_emits_event():
    log = EventLog()
    feed = PacingProtectionFeed(event_log=log)
    feed.assess_and_feed(SUBJECT, 100, 60, 1)
    emitted = log.of_type(EventType.PACING_SIGNAL_EMITTED)
    assert len(emitted) == 1
    assert emitted[0].payload["delivered_to_scheduler"] is True
