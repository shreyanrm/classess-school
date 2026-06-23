"""Raised-hand input, no-person-present signal, engagement<->performance link."""

from __future__ import annotations

import pytest

from app import events
from app.attention import (
    EngagementBand,
    EngagementPerformanceLink,
    NoPersonSignal,
    RaisedHand,
    no_person_event,
    performance_link_event,
    raised_hand_event,
    relate_engagement_to_performance,
)


def _uuid() -> str:
    return events.new_canonical_uuid()


# -- raised hand ------------------------------------------------------------
def test_explicit_raised_hand_is_always_accepted():
    hand = RaisedHand(subject_uuid=_uuid())
    assert hand.accepted
    ev = raised_hand_event("s1", hand)
    assert ev.kind is events.EventKind.RAISED_HAND
    assert ev.payload["from_vision"] is False
    assert ev.payload["punitive"] is False


def test_vision_raised_hand_gated_by_confidence():
    weak = RaisedHand(subject_uuid=_uuid(), confidence=0.4, from_vision=True)
    assert not weak.accepted
    assert raised_hand_event("s1", weak) is None
    strong = RaisedHand(subject_uuid=_uuid(), confidence=0.9, from_vision=True)
    assert strong.accepted
    assert raised_hand_event("s1", strong) is not None


def test_raised_hand_never_from_face():
    with pytest.raises(ValueError):
        RaisedHand(subject_uuid=_uuid(), from_face=True)


def test_raised_hand_requires_opaque_uuid():
    with pytest.raises(ValueError):
        RaisedHand(subject_uuid="Asha")


# -- no person present ------------------------------------------------------
def test_no_person_signal_gated_and_not_attendance():
    sig = NoPersonSignal(subject_uuid=_uuid(), confidence=0.8)
    ev = no_person_event("s1", sig)
    assert ev.kind is events.EventKind.NO_PERSON_PRESENT
    assert ev.payload["is_attendance"] is False
    assert ev.payload["punitive"] is False


def test_no_person_below_gate_is_held_back():
    sig = NoPersonSignal(subject_uuid=_uuid(), confidence=0.3)
    assert no_person_event("s1", sig) is None


def test_no_person_never_from_face():
    with pytest.raises(ValueError):
        NoPersonSignal(subject_uuid=_uuid(), confidence=0.9, from_face=True)


# -- engagement <-> later performance --------------------------------------
def test_low_engagement_low_score_flags_topic_to_revisit():
    link = relate_engagement_to_performance(
        _uuid(), "topic://fractions", EngagementBand.NEEDS_A_NUDGE, 0.3
    )
    assert "revisit" in link.relation
    assert link.assistive is True


def test_engaged_high_score_relation():
    link = relate_engagement_to_performance(
        _uuid(), "topic://fractions", EngagementBand.ENGAGED, 0.9
    )
    assert "performed well" in link.relation


def test_uncertain_engagement_yields_uncertain_relation():
    link = relate_engagement_to_performance(
        _uuid(), "topic://x", EngagementBand.UNCERTAIN, 0.5
    )
    assert "uncertain" in link.relation


def test_performance_link_event_is_non_punitive_non_identity_graded():
    link = relate_engagement_to_performance(
        _uuid(), "topic://x", EngagementBand.SETTLING, 0.6
    )
    ev = performance_link_event("s1", link)
    assert ev.kind is events.EventKind.ENGAGEMENT_PERFORMANCE_LINK
    assert ev.payload["punitive"] is False
    assert ev.payload["identity_graded"] is False


def test_link_validates_score_bounds_and_uuid():
    with pytest.raises(ValueError):
        EngagementPerformanceLink(
            subject_uuid=_uuid(),
            topic_ref="t",
            engagement_band=EngagementBand.ENGAGED,
            later_score=2.0,
            relation="x",
        )
    with pytest.raises(ValueError):
        relate_engagement_to_performance(
            "Asha", "t", EngagementBand.ENGAGED, 0.5
        )
