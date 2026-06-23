"""Response workflow: parent-comm trigger + catch-up plan on repeated absence."""

import datetime as _dt

from app.events import (
    CatchupPlanProposedEvent,
    EventType,
    ParentCommunicationRequestedEvent,
)
from app.response import (
    build_catchup_plan,
    catchup_plan_event,
    parent_communication_for,
    should_respond,
)
from app.risk import detect_risks


def _day(offset, status, subject=None):
    anchor = _dt.date(2026, 6, 22)
    d = (anchor - _dt.timedelta(days=offset)).isoformat()
    entry = {"date": d, "status": status}
    if subject:
        entry["subject"] = subject
    return entry


def test_consecutive_absence_triggers_parent_comm_request():
    days = [_day(i, "absent") for i in range(5)]
    findings = detect_risks({"canonical_uuid": "uuid-a", "days": days})
    consec = next(f for f in findings if f.risk_kind == "consecutive")
    event = parent_communication_for(consec)
    assert isinstance(event, ParentCommunicationRequestedEvent)
    assert event.event_type == EventType.PARENT_COMM_REQUESTED.value
    # never auto-sent: requires approval
    assert event.requires_approval is True
    assert "@" not in event.canonical_uuid


def test_watch_level_does_not_trigger_comm():
    # 2 consecutive absences -> WATCH severity, below the trigger threshold
    days = [_day(i, "absent") for i in range(2)]
    findings = detect_risks({"canonical_uuid": "uuid-a", "days": days})
    consec = next(f for f in findings if f.risk_kind == "consecutive")
    assert consec.severity == "watch"
    assert should_respond(consec) is False
    assert parent_communication_for(consec) is None


def test_catchup_plan_groups_missed_subjects():
    days = [
        _day(1, "absent", "maths"),
        _day(2, "absent", "maths"),
        _day(3, "absent", "science"),
        _day(4, "present", "english"),
    ]
    plan = build_catchup_plan("uuid-a", {"canonical_uuid": "uuid-a", "days": days})
    assert plan.missed_sessions == 3
    assert set(plan.subjects) == {"maths", "science"}
    assert plan.steps
    assert plan.requires_approval is True


def test_catchup_plan_event_requires_approval():
    days = [_day(1, "absent", "maths")]
    plan = build_catchup_plan("uuid-a", {"canonical_uuid": "uuid-a", "days": days})
    event = catchup_plan_event(plan)
    assert isinstance(event, CatchupPlanProposedEvent)
    assert event.requires_approval is True
    assert event.event_type == EventType.CATCHUP_PLAN_PROPOSED.value


def test_no_missed_days_empty_plan():
    days = [_day(i, "present") for i in range(5)]
    plan = build_catchup_plan("uuid-a", {"canonical_uuid": "uuid-a", "days": days})
    assert plan.missed_sessions == 0
    assert plan.steps == ()
