"""Continuity / handover notes: opaque refs, PII-free, consent-gated coaching."""

from __future__ import annotations

import pytest

from app.continuity import ContinuityNote, build_continuity_note


FROM_T = "tttt0000-0000-4000-8000-000000000001"
TO_T = "tttt0000-0000-4000-8000-000000000002"
TEACHER_CONSENT = "cccc0000-0000-4000-8000-000000000007"


def test_handover_note_is_complete_and_pii_free():
    note = build_continuity_note(
        section_id="S10B",
        subject_id="math",
        from_teacher_ref=FROM_T,
        reason="planned_leave",
        current_topic_id="topic_quadratics",
        to_teacher_ref=TO_T,
        next_topic_id="topic_polynomials",
        last_delivered_period=18,
        watch_points=["This group benefits from more retrieval practice"],
        prepared_materials=["content_pack_7"],
    )
    assert isinstance(note, ContinuityNote)
    assert note.is_complete is True
    assert "quadratics" in note.summary()
    # No name/email fields exist on the note at all.
    assert not hasattr(note, "from_teacher_name")


def test_watch_points_must_be_generic_strings():
    with pytest.raises(TypeError):
        ContinuityNote(
            section_id="S10B",
            subject_id="math",
            from_teacher_ref=FROM_T,
            reason="substitution",
            current_topic_id="topic_quadratics",
            watch_points=[{"student": "a named child"}],  # type: ignore[list-item]
        )


def test_coaching_note_travels_only_with_consent():
    # A shared coaching reflection without a consent ref is refused.
    with pytest.raises(PermissionError):
        build_continuity_note(
            section_id="S10B",
            subject_id="math",
            from_teacher_ref=FROM_T,
            reason="mentor_rotation",
            current_topic_id="topic_quadratics",
            next_topic_id="topic_polynomials",
            shared_coaching_note="I am working on wait time.",
        )
    # With the outgoing teacher's consent it travels.
    note = build_continuity_note(
        section_id="S10B",
        subject_id="math",
        from_teacher_ref=FROM_T,
        reason="mentor_rotation",
        current_topic_id="topic_quadratics",
        next_topic_id="topic_polynomials",
        shared_coaching_note="I am working on wait time.",
        coaching_consent_ref=TEACHER_CONSENT,
    )
    assert note.carries_coaching is True


def test_incomplete_when_next_topic_unset():
    note = build_continuity_note(
        section_id="S10B",
        subject_id="math",
        from_teacher_ref=FROM_T,
        reason="transfer",
        current_topic_id="topic_quadratics",
    )
    assert note.is_complete is False
    assert "to be set" in note.summary()


def test_why_am_i_seeing_this_disclaims_judgement():
    note = build_continuity_note(
        section_id="S10B", subject_id="math", from_teacher_ref=FROM_T,
        reason="planned_leave", current_topic_id="t1", next_topic_id="t2",
    )
    why = note.why_am_i_seeing_this().lower()
    assert "no student records" in why
    assert "no judgement" in why
