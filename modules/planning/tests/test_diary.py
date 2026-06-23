"""Teacher diary tracks planned vs delivered and auto-updates from signals."""

import pytest

from planning.app.events import EventLog, EventType
from planning.app.diary import (
    DeliveryStatus,
    DiaryEntry,
    TeacherDiary,
)

SUBJECT = "class-uuid"


def _diary(**kw):
    return TeacherDiary(owner_uuid="teacher-uuid", subject_uuid=SUBJECT, **kw)


def test_plan_creates_entries_marked_planned():
    diary = _diary()
    diary.plan_item("i1", outcome_ids=["o1"], planned_minutes=40)
    entry = diary.entry("i1")
    assert entry.status == DeliveryStatus.PLANNED
    assert entry.planned_minutes == 40
    assert entry.delivered_minutes == 0


def test_delivery_signal_marks_delivered():
    diary = _diary()
    diary.plan_item("i1", outcome_ids=["o1"], planned_minutes=40)
    diary.record_delivery("i1", delivered_minutes=40)
    entry = diary.entry("i1")
    assert entry.status == DeliveryStatus.DELIVERED
    assert entry.delivered_minutes == 40


def test_partial_delivery_is_tracked():
    diary = _diary()
    diary.plan_item("i1", outcome_ids=["o1"], planned_minutes=60)
    diary.record_delivery("i1", delivered_minutes=25)
    entry = diary.entry("i1")
    assert entry.status == DeliveryStatus.PARTIAL
    assert entry.delivered_minutes == 25


def test_not_delivered_item_remains_planned_and_counts_as_gap():
    diary = _diary()
    diary.plan_item("i1", outcome_ids=["o1"], planned_minutes=40)
    diary.plan_item("i2", outcome_ids=["o2"], planned_minutes=40)
    diary.record_delivery("i1", delivered_minutes=40)
    gaps = diary.undelivered()
    assert [e.item_id for e in gaps] == ["i2"]


def test_planned_vs_delivered_summary():
    diary = _diary()
    diary.plan_item("i1", outcome_ids=["o1"], planned_minutes=40)
    diary.plan_item("i2", outcome_ids=["o2"], planned_minutes=60)
    diary.record_delivery("i1", delivered_minutes=40)
    diary.record_delivery("i2", delivered_minutes=30)
    summary = diary.planned_vs_delivered()
    assert summary["planned_minutes"] == 100
    assert summary["delivered_minutes"] == 70
    assert summary["delivered_count"] == 1
    assert summary["partial_count"] == 1


def test_delivery_for_unknown_item_raises():
    diary = _diary()
    with pytest.raises(KeyError):
        diary.record_delivery("nope", delivered_minutes=10)


def test_diary_emits_planned_and_delivered_events():
    log = EventLog()
    diary = _diary(event_log=log)
    diary.plan_item("i1", outcome_ids=["o1"], planned_minutes=40)
    diary.record_delivery("i1", delivered_minutes=40)
    assert len(log.of_type(EventType.DIARY_PLANNED)) == 1
    assert len(log.of_type(EventType.DIARY_DELIVERED)) == 1


def test_diary_entry_carries_no_pii_only_uuid_and_outcomes():
    diary = _diary()
    diary.plan_item("i1", outcome_ids=["o1"], planned_minutes=40)
    entry = diary.entry("i1")
    assert isinstance(entry, DiaryEntry)
    assert entry.outcome_ids == ("o1",)
