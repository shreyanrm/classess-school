"""Events are immutable, append-only, and PII-free."""

import dataclasses

import pytest

from planning.app.events import (
    EventLog,
    EventType,
    PlanningEvent,
    PiiInPayloadError,
)


def test_event_requires_subject_uuid():
    with pytest.raises(ValueError):
        PlanningEvent(event_type=EventType.PLAN_DRAFTED, subject_uuid="")


def test_event_is_immutable():
    ev = PlanningEvent(EventType.PLAN_DRAFTED, "uuid-1", {"plan_id": "p1"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.subject_uuid = "uuid-2"  # type: ignore[misc]


def test_payload_rejects_pii_keys():
    for bad in ("student_name", "email", "guardian", "phone_number"):
        with pytest.raises(PiiInPayloadError):
            PlanningEvent(EventType.PLAN_DRAFTED, "uuid-1", {bad: "x"})


def test_payload_allows_ontology_slug_keys():
    # outcome_name_key is an ontology slug, not PII.
    ev = PlanningEvent(
        EventType.PLAN_OUTCOME_MAPPED,
        "uuid-1",
        {"outcome_name_key": "frac.add.like-denom"},
    )
    assert ev.payload["outcome_name_key"] == "frac.add.like-denom"


def test_log_is_append_only_and_has_no_mutation_api():
    log = EventLog()
    log.emit(EventType.PLAN_DRAFTED, "uuid-1", {"plan_id": "p1"})
    log.emit(EventType.PLAN_ADAPTED, "uuid-1", {"plan_id": "p2"})
    assert len(log) == 2
    # No update/delete surface exists.
    assert not hasattr(log, "update")
    assert not hasattr(log, "delete")
    assert not hasattr(log, "remove")


def test_log_sink_invoked_on_append():
    seen = []
    log = EventLog(sink=seen.append)
    log.emit(EventType.PLAN_DRAFTED, "uuid-1")
    assert len(seen) == 1
    assert seen[0].event_type == EventType.PLAN_DRAFTED


def test_redact_produces_successor_not_mutation():
    log = EventLog()
    original = log.emit(EventType.PLAN_DRAFTED, "uuid-1", {"plan_id": "p1"})
    successor = log.redact(original, {"plan_id": "p1", "corrected": True})
    assert successor.event_id != original.event_id
    assert original.payload == {"plan_id": "p1"}  # history untouched
    assert successor.payload["corrected"] is True


def test_filters_by_type_and_subject():
    log = EventLog()
    log.emit(EventType.PLAN_DRAFTED, "uuid-1")
    log.emit(EventType.PLAN_ADAPTED, "uuid-2")
    assert len(log.of_type(EventType.PLAN_DRAFTED)) == 1
    assert len(log.for_subject("uuid-2")) == 1
