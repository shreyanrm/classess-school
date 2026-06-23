"""Period launch assembled FROM a timetable entry (the doc's timetable bridge)."""

from __future__ import annotations

import pytest

from app import events
from app.board import ContentVerification, ObjectKind, new_content_ref, new_stroke
from app.period_launch import (
    AssessmentKind,
    AttendanceMethod,
    ContentItem,
    PeriodLaunch,
    TimetableEntry,
)


def _uuid() -> str:
    return events.new_canonical_uuid()


def test_timetable_entry_validates_topic_and_uuid():
    with pytest.raises(ValueError):
        TimetableEntry(session_id="s1", topic="", teacher_uuid=_uuid())
    with pytest.raises(ValueError):
        TimetableEntry(session_id="s1", topic="t", teacher_uuid="Teacher Bob")


def test_from_timetable_entry_carries_methods_and_content():
    teacher = _uuid()
    entry = TimetableEntry(
        session_id="s1",
        topic="Photosynthesis",
        teacher_uuid=teacher,
        title="Period 3 Biology",
        attendance_method=AttendanceMethod.PHOTO_SCAN,
        assessment_kind=AssessmentKind.DEVICE_FREE_ROOM_QUIZ,
    )
    v = ContentVerification(topic="Photosynthesis", confidence=0.9, cross_checked=True)
    content = [
        ContentItem(new_stroke(teacher, [(0, 0), (1, 1)])),
        ContentItem(new_content_ref(teacher, ObjectKind.SIMULATION, "sim://x", v), v),
    ]
    pl = PeriodLaunch.from_timetable_entry(entry, content)
    plan = pl.build()
    assert plan.topic == "Photosynthesis"
    assert plan.attendance_method is AttendanceMethod.PHOTO_SCAN
    assert plan.assessment_kind is AssessmentKind.DEVICE_FREE_ROOM_QUIZ
    # verified sim + plain stroke both shown
    assert plan.content_ready_count == 2


def test_from_timetable_entry_defers_unverified_content():
    teacher = _uuid()
    entry = TimetableEntry(session_id="s1", topic="Cells", teacher_uuid=teacher)
    v = ContentVerification(topic="Cells", confidence=0.4)  # below gate
    content = [ContentItem(new_content_ref(teacher, ObjectKind.MODEL_3D, "m://x", v), v)]
    plan = PeriodLaunch.from_timetable_entry(entry, content).build()
    assert plan.content_ready_count == 0
    assert len(plan.content_deferred) == 1


def test_from_timetable_entry_start_requires_approval():
    teacher = _uuid()
    entry = TimetableEntry(session_id="s1", topic="Cells", teacher_uuid=teacher)
    pl = PeriodLaunch.from_timetable_entry(entry)
    plan = pl.build()
    approval = pl.prepare_start(plan)
    assert approval.requires_approval is True
    assert approval.requested_by == teacher
