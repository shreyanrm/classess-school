"""Events are immutable, append-only, PII-free, and trigger substitution."""

import dataclasses

import pytest

from app.events import (
    EventType,
    catchup_plan_proposed_event,
    collect_append_only,
    conflict_flagged_event,
    correction_logged_event,
    mark_recorded_event,
    parent_communication_requested_event,
    risk_flagged_event,
    roll_confirmed_event,
    staff_recorded_event,
    substitution_needed_event,
    to_envelope,
)


def test_roll_confirmed_event_shape():
    e = roll_confirmed_event(
        "sess-1", "teacher-uuid", "absent-only",
        {"present": 28, "absent": 2, "late": 0, "excused": 0},
    )
    assert e.event_type == EventType.ROLL_CONFIRMED.value
    assert e.present == 28 and e.absent == 2
    assert e.schema_version >= 1
    assert e.source == "attendance"


def test_events_are_immutable():
    e = mark_recorded_event("s", "uuid-a", "present", "manual", "t-uuid")
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.status = "absent"  # type: ignore[misc]


def test_substitution_needed_event_is_the_trigger():
    e = substitution_needed_event("staff-1", "2026-06-22", ["sess-1", "sess-2"])
    assert e.event_type == EventType.SUBSTITUTION_NEEDED.value
    # crosses into the scheduling domain by event name
    assert e.event_type.startswith("scheduling.")
    assert e.session_ids == ("sess-1", "sess-2")


def test_risk_event_carries_explanation_and_review():
    e = risk_flagged_event(
        "uuid-a", "consecutive", "concern", "absent 4 days running", 4
    )
    assert e.risk_kind == "consecutive"
    assert e.needs_human_review is True
    assert e.explanation


def test_conflict_event_lists_methods():
    e = conflict_flagged_event(
        "s", "uuid-a", ["photo-roster", "absent-only"], ["absent", "present"]
    )
    assert e.event_type == EventType.CONFLICT_FLAGGED.value
    assert e.needs_human_review is True
    assert len(e.methods) == 2


def test_pii_identifier_rejected_in_events():
    with pytest.raises(ValueError):
        mark_recorded_event("s", "kid@example.com", "present", "manual", "t")
    with pytest.raises(ValueError):
        staff_recorded_event("staff-1", "absent", "2026-06-22", "+1 555 123 4567")


def test_append_only_log_does_not_mutate_input():
    log = []
    e = roll_confirmed_event("s", "t", "manual", {"present": 1})
    new_log = collect_append_only(log, e)
    assert log == []  # original untouched
    assert len(new_log) == 1
    assert new_log[0]["event_type"] == EventType.ROLL_CONFIRMED.value


def test_envelope_shape():
    e = substitution_needed_event("staff-1", "2026-06-22", ["sess-1"])
    env = to_envelope(e)
    for key in ("event_id", "event_type", "schema_version", "source",
                "occurred_at", "payload"):
        assert key in env


def test_correction_logged_event_carries_audit():
    e = correction_logged_event(
        "s", "uuid-a", "absent", "present", "head-uuid", "approved leave"
    )
    assert e.event_type == EventType.CORRECTION_LOGGED.value
    assert e.previous_status == "absent"
    assert e.corrected_status == "present"
    assert e.corrected_by == "head-uuid"


def test_parent_comm_request_requires_approval():
    e = parent_communication_requested_event(
        "uuid-a", "consecutive", "concern", "absent 4 days running"
    )
    assert e.event_type == EventType.PARENT_COMM_REQUESTED.value
    # crosses into the communication domain by event name
    assert e.event_type.startswith("communication.")
    assert e.requires_approval is True


def test_catchup_plan_event_requires_approval():
    e = catchup_plan_proposed_event("uuid-a", 3, ["maths", "science"])
    assert e.event_type == EventType.CATCHUP_PLAN_PROPOSED.value
    assert e.requires_approval is True
    assert e.missed_sessions == 3


def test_pii_rejected_in_new_events():
    with pytest.raises(ValueError):
        correction_logged_event(
            "s", "kid@example.com", "absent", "present", "h", "r"
        )
    with pytest.raises(ValueError):
        parent_communication_requested_event(
            "kid@example.com", "chronic", "urgent", "r"
        )
