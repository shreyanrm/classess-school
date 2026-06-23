"""Period launch: assemble content + attendance + assessment; staged start."""

from __future__ import annotations

import pytest

from app import events
from app.board import ContentVerification, ObjectKind, new_content_ref, new_stroke
from app.period_launch import (
    AssessmentKind,
    AttendanceMethod,
    ContentItem,
    PeriodLaunch,
)
from app.polls import ChildSafetyError


def _uuid() -> str:
    return events.new_canonical_uuid()


def test_assembles_content_attendance_assessment():
    teacher = _uuid()
    pl = PeriodLaunch("s1", "Photosynthesis", teacher, title="Period 3 Biology")
    pl.add_content(ContentItem(new_stroke(teacher, [(0, 0), (1, 1)])))
    pl.set_attendance(AttendanceMethod.PHOTO_SCAN)
    pl.set_assessment(AssessmentKind.DEVICE_FREE_ROOM_QUIZ)
    plan = pl.build()
    assert plan.topic == "Photosynthesis"
    assert plan.attendance_method is AttendanceMethod.PHOTO_SCAN
    assert plan.assessment_kind is AssessmentKind.DEVICE_FREE_ROOM_QUIZ
    assert plan.has_assessment
    assert plan.content_ready_count == 1


def test_verified_content_shown_unverified_deferred():
    teacher = _uuid()
    pl = PeriodLaunch("s1", "Cells", teacher)
    good = new_content_ref(
        teacher, ObjectKind.MODEL_3D, "model://cell",
        ContentVerification(topic="Cells", confidence=0.9, cross_checked=True),
    )
    bad = new_content_ref(
        teacher, ObjectKind.SIMULATION, "sim://x",
        ContentVerification(topic="Cells", confidence=0.4),
    )
    pl.add_content(ContentItem(good)).add_content(ContentItem(bad))
    plan = pl.build()
    assert plan.content_ready_count == 1
    assert len(plan.content_deferred) == 1


def test_start_is_staged_and_requires_human_approval():
    teacher = _uuid()
    pl = PeriodLaunch("s1", "Topic", teacher)
    plan = pl.build()
    approval = pl.prepare_start(plan)
    # consequential: never auto-starts; returns a requires_approval marker
    assert approval.requires_approval is True
    assert approval.session_id == "s1"
    assert approval.requested_by == teacher


def test_launched_event_carries_counts_and_no_pii():
    teacher = _uuid()
    pl = PeriodLaunch("s1", "Topic", teacher)
    pl.set_attendance(AttendanceMethod.VOICE_ROLL_CALL)
    pl.set_assessment(AssessmentKind.LIVE_QUIZ)
    plan = pl.build()
    ev = pl.launched_event(plan)
    assert ev.kind is events.EventKind.PERIOD_LAUNCHED
    assert ev.subject_uuid == teacher
    assert ev.payload["attendance_method"] == "voice_roll_call"
    assert ev.payload["assessment_kind"] == "live_quiz"
    assert "name" not in ev.payload


def test_title_is_child_safety_screened():
    with pytest.raises(ChildSafetyError):
        PeriodLaunch("s1", "Topic", _uuid(), title="how to make a weapon")


def test_teacher_must_be_opaque_uuid():
    with pytest.raises(ValueError):
        PeriodLaunch("s1", "Topic", "Teacher Bob")


def test_degrades_with_defaults_when_minimal():
    pl = PeriodLaunch("s1", "Topic", _uuid())
    plan = pl.build()
    assert plan.attendance_method is AttendanceMethod.MANUAL
    assert plan.assessment_kind is AssessmentKind.NONE
    assert not plan.has_assessment
