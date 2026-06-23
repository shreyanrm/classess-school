"""Capture ASSISTS but never auto-finalises; offline-capable shape."""

import pytest

from app.capture import (
    DraftRoll,
    Method,
    Status,
    VoiceMark,
    capture_absent_only,
    capture_online_presence,
    capture_photo_roster,
    capture_photo_scan,
    capture_voice,
    confirm_roll,
    summarize_draft,
)

ROSTER = ["uuid-a", "uuid-b", "uuid-c"]


def test_photo_scan_returns_draft_never_final():
    draft = capture_photo_scan("sess-1", {"uuid-a": "p", "uuid-b": "absent"})
    assert isinstance(draft, DraftRoll)
    assert draft.status == "draft"
    assert draft.is_final is False
    assert draft.confirmed_by is None
    assert draft.method is Method.PHOTO_SCAN


def test_every_method_produces_a_draft_only():
    drafts = [
        capture_photo_scan("s", {"uuid-a": "p"}),
        capture_voice("s", [VoiceMark("uuid-a", "present", 0.9)]),
        capture_photo_roster("s", ROSTER, {"uuid-a": 0.95}),
        capture_absent_only("s", ROSTER, ["uuid-b"]),
        capture_online_presence("s", ROSTER, {"uuid-a": 600}, 300),
    ]
    for d in drafts:
        assert d.status == "draft"
        assert d.is_final is False
        assert d.confirmed_by is None


def test_absent_only_suggests_present_for_rest():
    draft = capture_absent_only("s", ROSTER, ["uuid-b"])
    by = {m.canonical_uuid: m.status for m in draft.marks}
    assert by["uuid-b"] is Status.ABSENT
    assert by["uuid-a"] is Status.PRESENT
    assert by["uuid-c"] is Status.PRESENT


def test_online_presence_late_and_absent():
    draft = capture_online_presence(
        "s", ROSTER, {"uuid-a": 600, "uuid-b": 60}, 300
    )
    by = {m.canonical_uuid: m.status for m in draft.marks}
    assert by["uuid-a"] is Status.PRESENT
    assert by["uuid-b"] is Status.LATE
    assert by["uuid-c"] is Status.ABSENT


def test_photo_roster_undetected_flagged_for_review():
    draft = capture_photo_roster("s", ROSTER, {"uuid-a": 0.95})
    undetected = [m for m in draft.marks if m.canonical_uuid != "uuid-a"]
    assert all(m.needs_review for m in undetected)


def test_confirm_requires_human():
    draft = capture_absent_only("s", ROSTER, ["uuid-b"])
    with pytest.raises(ValueError):
        confirm_roll(draft, confirmed_by="")
    with pytest.raises(ValueError):
        confirm_roll(draft, confirmed_by="   ")


def test_confirm_finalises_and_is_immutable():
    draft = capture_absent_only("s", ROSTER, ["uuid-b"])
    final = confirm_roll(draft, confirmed_by="teacher-uuid")
    assert final.is_final is True
    assert final.confirmed_by == "teacher-uuid"
    assert final.confirmed_at is not None
    # original draft object unchanged (immutable / append-only shape)
    assert draft.is_final is False
    # cannot re-confirm an already-final roll
    with pytest.raises(ValueError):
        confirm_roll(final, confirmed_by="teacher-uuid")


def test_confirm_allows_human_override():
    draft = capture_absent_only("s", ROSTER, ["uuid-b"])
    final = confirm_roll(
        draft,
        confirmed_by="teacher-uuid",
        overrides={"uuid-a": Status.ABSENT},
    )
    by = {m.canonical_uuid: m.status for m in final.marks}
    assert by["uuid-a"] is Status.ABSENT


def test_confirm_rejects_unsafe_note():
    draft = capture_absent_only("s", ROSTER, ["uuid-b"])
    with pytest.raises(ValueError):
        confirm_roll(draft, confirmed_by="t", note="student said suicide")


def test_low_confidence_marks_need_review():
    draft = capture_voice(
        "s",
        [VoiceMark("uuid-a", "present", 0.2)],
    )
    assert draft.marks[0].needs_review is True
    assert draft.review_queue


def test_summarize_draft_counts():
    draft = capture_absent_only("s", ROSTER, ["uuid-b"])
    counts = summarize_draft(draft)
    assert counts["absent"] == 1
    assert counts["present"] == 2
    assert "needs_review" in counts


def test_no_pii_only_uuids_in_marks():
    draft = capture_absent_only("s", ROSTER, ["uuid-b"])
    for m in draft.marks:
        assert "@" not in m.canonical_uuid


def test_session_id_required():
    with pytest.raises(ValueError):
        capture_absent_only("", ROSTER, [])
