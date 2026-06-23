"""Event emission: append-only, opaque-only, degrades offline, approval-gated."""

from __future__ import annotations

import pytest

from app.config import SchedulingSettings
from app.events import (
    EventEmitter,
    build_attendance_trigger_payload,
    build_pacing_drift_payload,
    build_timetable_changed_payload,
)


INST = "11110000-0000-4000-8000-000000000001"
CANON = "9999aaaa-0000-4000-8000-000000000001"
CONSENT = "cccccccc-0000-4000-8000-000000000003"
APPROVER = "dddd0000-0000-4000-8000-000000000009"


def test_emitter_degrades_to_in_memory_sink_with_no_gateway():
    emitter = EventEmitter(SchedulingSettings())  # nothing configured.
    assert emitter.degraded is True
    assert "in-memory" in emitter.sink_label
    # The dotted NAMES (never values) of the missing vars are reported.
    assert "clss.scheduling.dev.gateway_url" in emitter.sink_label


def test_attendance_trigger_round_trips_through_envelope():
    emitter = EventEmitter(SchedulingSettings())
    result = emitter.emit_attendance_trigger(
        canonical_uuid=CANON,
        consent_ref=CONSENT,
        institution_id=INST,
        period_id="p1",
        section_id="S10B",
        on_date="2026-06-22",
        reason="teacher_absent",
    )
    assert result.delivered is False  # local-only in the degraded path.
    env = result.envelope
    assert env["type"] == "attendance.trigger"
    assert env["purpose"] == "operations"
    assert env["canonical_uuid"] == CANON
    assert env["schema_version"] == "v1"
    # Append-only: the buffer holds the event and is never mutated/deleted.
    assert emitter.buffered() == [env]


def test_pacing_drift_payload_carries_evidence_and_owner():
    payload = build_pacing_drift_payload(
        institution_id=INST,
        section_id="S10B",
        subject_id="math",
        band="behind",
        expected_periods=20.0,
        delivered_periods=14,
        drift_periods=6.0,
        owner_ref=APPROVER,
    )
    assert payload["band"] == "behind"
    assert payload["drift_periods"] == 6.0
    assert payload["owner_ref"] == APPROVER


def test_timetable_changed_requires_an_approver():
    # Recording a timetable change without an approver is refused (INVARIANT 8).
    with pytest.raises(PermissionError):
        build_timetable_changed_payload(
            institution_id=INST,
            period_id="p1",
            section_id="S10B",
            change_kind="substitution",
            approved_by="",
        )
    # With an approver it builds and carries the opaque approver ref.
    payload = build_timetable_changed_payload(
        institution_id=INST,
        period_id="p1",
        section_id="S10B",
        change_kind="substitution",
        approved_by=APPROVER,
        new_teacher_ref="bbbb0000-0000-4000-8000-000000000002",
    )
    assert payload["approved_by"] == APPROVER


def test_no_pii_fields_in_any_payload():
    payload = build_attendance_trigger_payload(
        institution_id=INST,
        period_id="p1",
        section_id="S10B",
        on_date="2026-06-22",
        reason="room_lost",
    )
    forbidden = {"name", "email", "phone", "first_name", "last_name", "dob"}
    assert not (forbidden & set(payload.keys()))


def test_appends_are_immutable_across_multiple_emits():
    emitter = EventEmitter(SchedulingSettings())
    emitter.emit_attendance_trigger(
        canonical_uuid=CANON, consent_ref=CONSENT, institution_id=INST,
        period_id="p1", section_id="S10B", on_date="2026-06-22", reason="teacher_absent",
    )
    first_snapshot = emitter.buffered()
    emitter.emit_pacing_drift(
        canonical_uuid=CANON, consent_ref=CONSENT, institution_id=INST,
        section_id="S10B", subject_id="math", band="behind",
        expected_periods=20.0, delivered_periods=14, drift_periods=6.0, owner_ref=APPROVER,
    )
    # The earlier snapshot is unchanged (append-only; never mutated in place).
    assert len(first_snapshot) == 1
    assert len(emitter.buffered()) == 2
