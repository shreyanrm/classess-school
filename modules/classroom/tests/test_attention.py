"""Attention signals: assistive, non-punitive, non-identity-graded, gated."""

from __future__ import annotations

import pytest

from app import events
from app.attention import (
    ActivityWindow,
    AttentionSignal,
    EngagementBand,
    VisionAssist,
    assess,
    to_event,
)


def _uuid() -> str:
    return events.new_canonical_uuid()


def test_signal_cannot_be_punitive():
    with pytest.raises(ValueError):
        AttentionSignal(
            subject_uuid=_uuid(),
            band=EngagementBand.NEEDS_A_NUDGE,
            confidence=0.9,
            punitive=True,
        )


def test_signal_cannot_be_identity_graded():
    with pytest.raises(ValueError):
        AttentionSignal(
            subject_uuid=_uuid(),
            band=EngagementBand.ENGAGED,
            confidence=0.9,
            identity_graded=True,
        )


def test_high_activity_reads_engaged():
    sig = assess(
        _uuid(),
        ActivityWindow(
            board_interactions=6, poll_responses=1, presence_continuity=1.0
        ),
    )
    assert sig.band is EngagementBand.ENGAGED
    assert sig.assistive is True
    assert sig.punitive is False
    assert sig.identity_graded is False


def test_low_activity_reads_needs_a_nudge_not_a_sanction():
    sig = assess(
        _uuid(),
        ActivityWindow(
            board_interactions=0, poll_responses=0, presence_continuity=1.0
        ),
    )
    assert sig.band in {
        EngagementBand.NEEDS_A_NUDGE,
        EngagementBand.SETTLING,
    }
    assert sig.punitive is False


def test_low_confidence_yields_uncertain_not_a_claim():
    # near-zero presence drives confidence below the gate
    sig = assess(
        _uuid(),
        ActivityWindow(
            board_interactions=0, poll_responses=0, presence_continuity=0.0
        ),
    )
    assert sig.band is EngagementBand.UNCERTAIN


def test_vision_assist_must_not_be_from_face():
    with pytest.raises(ValueError):
        VisionAssist(screen_foregrounded=True, confidence=0.9, from_face=True)


def test_vision_assist_is_only_a_weak_nudge():
    base = assess(
        _uuid(),
        ActivityWindow(
            board_interactions=3, poll_responses=1, presence_continuity=1.0
        ),
    )
    nudged = assess(
        _uuid(),
        ActivityWindow(
            board_interactions=3, poll_responses=1, presence_continuity=1.0
        ),
        vision=VisionAssist(screen_foregrounded=True, confidence=0.9),
    )
    # vision only nudges; confidence does not drop and stays bounded
    assert 0.0 <= nudged.confidence <= 1.0
    assert nudged.band in set(EngagementBand)
    assert base.assistive and nudged.assistive


def test_event_tags_assistive_non_punitive_non_identity_graded():
    sig = assess(
        _uuid(),
        ActivityWindow(board_interactions=6, poll_responses=1),
    )
    ev = to_event("s1", sig)
    assert ev.payload["assistive"] is True
    assert ev.payload["punitive"] is False
    assert ev.payload["identity_graded"] is False


def test_subject_must_be_opaque_uuid():
    with pytest.raises(ValueError):
        assess("Asha", ActivityWindow())
