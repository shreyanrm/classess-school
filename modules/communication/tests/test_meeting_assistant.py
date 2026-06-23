"""Silent meeting assistant: captures ONLY with consent; produces notes, key
points, and PREPARED (never auto-fired) action items with owner+timeline+follow-up."""

from __future__ import annotations

import pytest

from app.config import CommunicationSettings
from app.meeting_assistant import (
    MeetingConsentError,
    SilentMeetingAssistant,
    TranscriptSegment,
)


MEETING = "meeting-0000-4000-8000-000000000050"
CONSENT = "cccccccc-0000-4000-8000-000000000050"


def _assistant() -> SilentMeetingAssistant:
    return SilentMeetingAssistant(CommunicationSettings())


def _segments() -> list[TranscriptSegment]:
    return [
        TranscriptSegment("teacher", "Your child has made strong progress in reading."),
        TranscriptSegment("parent", "That is lovely to hear."),
        TranscriptSegment("teacher", "We will send home a short reading list this week."),
        TranscriptSegment("parent", "I will read with them most evenings."),
    ]


def test_capture_without_consent_is_refused():
    with pytest.raises(MeetingConsentError):
        _assistant().capture(consent_ref=None, segments=_segments())


def test_synthesise_without_consent_is_refused():
    with pytest.raises(MeetingConsentError):
        _assistant().synthesise(meeting_id=MEETING, consent_ref=None, segments=_segments())


def test_consented_synthesis_produces_notes_key_points_and_actions():
    notes = _assistant().synthesise(
        meeting_id=MEETING, consent_ref=CONSENT, segments=_segments()
    )
    assert notes.notes
    assert notes.key_points  # the salient points.
    assert notes.action_items  # the two "will" cues become action items.
    assert notes.segment_count == 4


def test_action_items_are_proposed_not_auto_fired():
    notes = _assistant().synthesise(
        meeting_id=MEETING, consent_ref=CONSENT, segments=_segments()
    )
    for item in notes.action_items:
        assert item.status == "proposed"   # permission ladder — never auto-fired.
        assert item.owner_role            # an owner role is proposed.
        assert item.timeline              # a timeline.
        assert item.follow_up             # a follow-up.


def test_notes_retain_roles_not_names():
    notes = _assistant().synthesise(
        meeting_id=MEETING, consent_ref=CONSENT, segments=_segments()
    )
    assert "teacher" in notes.notes or "parent" in notes.notes
    assert "no names" in notes.notes.lower()


def test_no_live_capture_without_a_transcription_provider():
    a = _assistant()
    assert a.can_live_capture is False  # nothing wired.
    notes = a.synthesise(meeting_id=MEETING, consent_ref=CONSENT, segments=_segments())
    assert notes.captured_with == "supplied_segments"
