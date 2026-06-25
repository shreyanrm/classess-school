"""PTM lifecycle: booking is permission-gated (proposed -> human-confirmed);
pre-submitted questions are child-safety screened before they reach a teacher;
the follow-up plan is partnership-shaped with the parent's part highlighted."""

from __future__ import annotations

import pytest

from app.config import CommunicationSettings
from app.meeting_assistant import SilentMeetingAssistant, TranscriptSegment
from app.ptm import (
    BookingApprovalError,
    BookingStatus,
    MeetingSlot,
    PtmQuestionFlaggedError,
    PtmService,
)


PARENT = "9999aaaa-0000-4000-8000-000000000200"
TEACHER = "9999aaaa-0000-4000-8000-000000000201"
CHILD_CTX = "ctx-child-0000-4000-8000-000000000202"
MEETING = "meeting-0000-4000-8000-000000000203"
CONSENT = "cccccccc-0000-4000-8000-000000000204"


def _service() -> PtmService:
    return PtmService(settings=CommunicationSettings())  # nothing wired.


def _slot() -> MeetingSlot:
    return MeetingSlot(
        slot_id="slot-1",
        owner_ref=TEACHER,
        owner_role="teacher",
        starts_at="2026-07-03T15:30:00+00:00",
        window_label="Fri 3:30–3:45pm",
    )


def _booking(service: PtmService):
    return service.request_booking(
        slot=_slot(), parent_ref=PARENT, child_context_ref=CHILD_CTX
    )


# -- 1. Booking is permission-gated ---------------------------------------

def test_a_requested_booking_is_proposed_not_yet_scheduled():
    booking = _booking(_service())
    assert booking.status is BookingStatus.PROPOSED
    assert booking.is_confirmed is False
    assert booking.participant_refs == [PARENT, TEACHER]
    assert booking.scheduled_for == "2026-07-03T15:30:00+00:00"


def test_confirm_requires_a_human_and_then_schedules():
    service = _service()
    booking = _booking(service)
    with pytest.raises(BookingApprovalError):
        service.confirm_booking(booking.booking_id, by_ref=None)  # no human.
    confirmed = service.confirm_booking(booking.booking_id, by_ref=TEACHER)
    assert confirmed.is_confirmed is True
    assert confirmed.confirmed_by_ref == TEACHER


def test_declined_booking_cannot_be_confirmed():
    service = _service()
    booking = _booking(service)
    booking.decline(by_ref=TEACHER)
    with pytest.raises(BookingApprovalError):
        booking.confirm(by_ref=TEACHER)


def test_cancel_requires_a_human():
    booking = _booking(_service())
    booking.confirm(by_ref=TEACHER)
    with pytest.raises(BookingApprovalError):
        booking.cancel(by_ref=None)
    booking.cancel(by_ref=TEACHER)
    assert booking.status is BookingStatus.CANCELLED


def test_no_reminders_until_the_booking_is_confirmed():
    service = _service()
    booking = _booking(service)
    with pytest.raises(BookingApprovalError):
        service.reminders_for(booking, when_label="tomorrow at 3:30pm")
    booking.confirm(by_ref=TEACHER)
    reminders = service.reminders_for(booking, when_label="tomorrow at 3:30pm")
    assert {r.recipient_ref for r in reminders} == {PARENT, TEACHER}
    # Reminders carry a plain window + body, never contact details.
    for r in reminders:
        assert "tomorrow at 3:30pm" in r.when_label
        assert r.body


# -- 2. Prep: pre-submitted questions are screened, then reach the teacher --

def test_clean_questions_reach_the_teachers_prep():
    service = _service()
    booking = _booking(service)
    prep = service.prepare(
        booking=booking,
        child_brief="Aanya is making steady progress; reading is a strength.",
        question_bodies=[
            "How can I help with word problems at home?",
            "Is there a reading list you'd recommend?",
        ],
    )
    assert prep.question_count == 2
    assert prep.child_brief
    for q in prep.questions:
        assert q.finding.flagged is False  # clean questions are admitted.


def test_a_flagged_question_does_not_silently_route_to_the_teacher():
    service = _service()
    booking = _booking(service)
    with pytest.raises(PtmQuestionFlaggedError):
        service.prepare(
            booking=booking,
            child_brief="brief",
            question_bodies=["i want to die"],  # safeguarding matter, not routed.
        )


def test_prep_with_no_questions_still_gives_a_brief():
    service = _service()
    booking = _booking(service)
    prep = service.prepare(booking=booking, child_brief="A short shared picture.")
    assert prep.question_count == 0
    assert prep.child_brief == "A short shared picture."


# -- 3. Follow-up: shared plan, parent's part highlighted ------------------

def _notes():
    assistant = SilentMeetingAssistant(CommunicationSettings())
    segments = [
        TranscriptSegment("teacher", "We will send home a short reading list this week."),
        TranscriptSegment("parent", "I will read with them most evenings."),
        TranscriptSegment("teacher", "That sounds lovely."),
    ]
    return assistant.synthesise(meeting_id=MEETING, consent_ref=CONSENT, segments=segments)


def test_follow_up_highlights_the_parents_part_and_is_not_auto_assigned():
    service = _service()
    booking = _booking(service)
    plan = service.follow_up(booking=booking, notes=_notes())
    assert plan.actions  # the two "will" cues became actions.
    # The parent's items are highlighted as their part.
    assert plan.parent_items
    assert all(a.is_parent_item for a in plan.parent_items)
    # Nothing is assigned until a human owns it (permission ladder).
    for a in plan.actions:
        assert a.is_assigned is False
        assert a.owner_role and a.due and a.follow_up


def test_assigning_an_owner_requires_a_human():
    service = _service()
    booking = _booking(service)
    plan = service.follow_up(booking=booking, notes=_notes())
    action = plan.actions[0]
    with pytest.raises(BookingApprovalError):
        action.assign_to(owner_ref=PARENT, by_ref=None)  # never auto-assigns.
    assigned = action.assign_to(owner_ref=PARENT, by_ref=TEACHER)
    assert assigned.is_assigned is True
    assert assigned.owner_ref == PARENT


def test_follow_up_with_no_actions_is_a_calm_check_in():
    service = _service()
    booking = _booking(service)
    assistant = SilentMeetingAssistant(CommunicationSettings())
    # Segments with no action cues -> no agreed actions.
    notes = assistant.synthesise(
        meeting_id=MEETING,
        consent_ref=CONSENT,
        segments=[TranscriptSegment("teacher", "Your child is doing well.")],
    )
    plan = service.follow_up(booking=booking, notes=notes)
    assert plan.actions == ()
    assert "calm" in plan.summary.lower()
