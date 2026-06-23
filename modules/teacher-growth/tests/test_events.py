"""Event emission: append-only, opaque-only, PRIVATE coaching, approval-gated."""

from __future__ import annotations

import pytest

from app.config import TeacherGrowthSettings
from app.events import (
    EventEmitter,
    build_coaching_signal_payload,
    build_handover_recorded_payload,
    build_review_signed_off_payload,
)


CANON = "9999aaaa-0000-4000-8000-000000000001"
CONSENT = "cccccccc-0000-4000-8000-000000000003"
TEACHER = "tttt0000-0000-4000-8000-000000000001"
REVIEWER = "rrrr0000-0000-4000-8000-000000000002"


def test_emitter_degrades_to_in_memory_sink_with_no_gateway():
    emitter = EventEmitter(TeacherGrowthSettings())  # nothing configured.
    assert emitter.degraded is True
    assert "in-memory" in emitter.sink_label
    # The dotted NAMES (never values) of the missing vars are reported.
    assert "clss.teachergrowth.dev.gateway_url" in emitter.sink_label


def test_coaching_signal_event_is_always_private_teacher_first():
    emitter = EventEmitter(TeacherGrowthSettings())
    result = emitter.emit_coaching_signal(
        canonical_uuid=CANON,
        consent_ref=CONSENT,
        teacher_ref=TEACHER,
        lesson_id="lesson_a",
        dimension="talk_ratio",
        direction="growth_area",
        confidence="high",
    )
    env = result.envelope
    assert env["type"] == "coaching.signal_generated"
    # Privacy is stamped on the envelope, not left to the caller.
    assert env["private"] is True
    assert env["visibility"] == "teacher_first"
    assert env["payload"]["private"] is True
    assert result.delivered is False  # local-only in the degraded path.
    assert emitter.buffered() == [env]


def test_coaching_event_forces_private_even_if_caller_tries_public():
    from app.events import build_envelope

    env = build_envelope(
        canonical_uuid=CANON,
        consent_ref=CONSENT,
        payload={"teacher_ref": TEACHER},
        event_type="coaching.signal_generated",
        private=False,            # caller attempt to make it public...
        visibility="public",      # ...is overridden.
    )
    assert env["private"] is True
    assert env["visibility"] == "teacher_first"


def test_review_signed_off_requires_a_human():
    with pytest.raises(PermissionError):
        build_review_signed_off_payload(
            review_id="rev1", teacher_ref=TEACHER, cycle="2026-T1", signed_off_by="",
        )
    payload = build_review_signed_off_payload(
        review_id="rev1", teacher_ref=TEACHER, cycle="2026-T1", signed_off_by=REVIEWER,
    )
    assert payload["signed_off_by"] == REVIEWER


def test_coaching_payload_carries_no_freetext_reading_or_score():
    payload = build_coaching_signal_payload(
        teacher_ref=TEACHER, lesson_id="l", dimension="wait_time",
        direction="strength", confidence="medium",
    )
    # The private free-text reading stays with the teacher; no score/rank leaks.
    assert "reading" not in payload
    assert "score" not in payload
    assert "rank" not in payload
    assert "rating" not in payload


def test_no_pii_fields_in_any_payload():
    payloads = [
        build_coaching_signal_payload(
            teacher_ref=TEACHER, lesson_id="l", dimension="talk_ratio",
            direction="neutral", confidence="low",
        ),
        build_review_signed_off_payload(
            review_id="r", teacher_ref=TEACHER, cycle="2026-T1", signed_off_by=REVIEWER,
        ),
        build_handover_recorded_payload(
            section_id="S10B", subject_id="math", from_teacher_ref=TEACHER,
            reason="planned_leave", current_topic_id="t1",
        ),
    ]
    forbidden = {"name", "email", "phone", "first_name", "last_name", "dob"}
    for payload in payloads:
        assert not (forbidden & set(payload.keys()))


def test_appends_are_immutable_across_multiple_emits():
    emitter = EventEmitter(TeacherGrowthSettings())
    emitter.emit_coaching_signal(
        canonical_uuid=CANON, consent_ref=CONSENT, teacher_ref=TEACHER,
        lesson_id="l", dimension="talk_ratio", direction="strength", confidence="high",
    )
    first_snapshot = emitter.buffered()
    emitter.emit_handover_recorded(
        canonical_uuid=CANON, consent_ref=CONSENT, section_id="S10B",
        subject_id="math", from_teacher_ref=TEACHER, reason="transfer",
        current_topic_id="t1",
    )
    # The earlier snapshot is unchanged (append-only; never mutated in place).
    assert len(first_snapshot) == 1
    assert len(emitter.buffered()) == 2
