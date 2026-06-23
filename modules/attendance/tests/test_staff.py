"""Staff attendance: drafts, human confirmation, substitution trigger."""

import pytest

from app.events import SubstitutionNeededEvent
from app.staff import (
    StaffStatus,
    build_substitution_request,
    confirm_staff,
    daily_summary,
    record_staff,
)


def test_record_is_draft_not_confirmed():
    rec = record_staff("staff-1", "2026-06-22", StaffStatus.ABSENT, ["sess-1"])
    assert rec.state == "draft"
    assert rec.is_confirmed is False
    assert rec.needs_substitution is False  # not confirmed yet


def test_substitution_only_after_confirmation():
    rec = record_staff("staff-1", "2026-06-22", StaffStatus.ABSENT, ["sess-1"])
    # no request before confirmation
    assert build_substitution_request(rec) is None
    confirmed = confirm_staff(rec, confirmed_by="head-uuid")
    assert confirmed.is_confirmed is True
    event = build_substitution_request(confirmed)
    assert isinstance(event, SubstitutionNeededEvent)
    assert event.staff_uuid == "staff-1"
    assert event.session_ids == ("sess-1",)
    assert event.reason == "staff_absent"


def test_present_staff_no_substitution():
    rec = record_staff("staff-1", "2026-06-22", StaffStatus.PRESENT, ["sess-1"])
    confirmed = confirm_staff(rec, confirmed_by="head-uuid")
    assert build_substitution_request(confirmed) is None


def test_absent_without_sessions_no_substitution():
    rec = record_staff("staff-1", "2026-06-22", StaffStatus.ABSENT, [])
    confirmed = confirm_staff(rec, confirmed_by="head-uuid")
    assert build_substitution_request(confirmed) is None


def test_confirm_requires_human():
    rec = record_staff("staff-1", "2026-06-22", StaffStatus.ABSENT, ["sess-1"])
    with pytest.raises(ValueError):
        confirm_staff(rec, confirmed_by="")


def test_confirm_is_immutable():
    rec = record_staff("staff-1", "2026-06-22", StaffStatus.ABSENT, ["sess-1"])
    confirmed = confirm_staff(rec, confirmed_by="head-uuid")
    assert rec.is_confirmed is False  # original unchanged
    with pytest.raises(ValueError):
        confirm_staff(confirmed, confirmed_by="head-uuid")


def test_unsafe_note_rejected():
    rec = record_staff("staff-1", "2026-06-22", StaffStatus.ABSENT, ["sess-1"])
    with pytest.raises(ValueError):
        confirm_staff(rec, confirmed_by="head-uuid", note="abuse at home")


def test_pii_identifier_rejected():
    with pytest.raises(ValueError):
        record_staff("teacher@example.com", "2026-06-22", StaffStatus.ABSENT)


def test_daily_summary():
    recs = [
        confirm_staff(
            record_staff("s1", "2026-06-22", StaffStatus.ABSENT, ["x"]),
            confirmed_by="h",
        ),
        record_staff("s2", "2026-06-22", StaffStatus.PRESENT),
    ]
    summary = daily_summary(recs)
    assert summary["absent"] == 1
    assert summary["present"] == 1
    assert summary["needs_substitution"] == 1
    assert summary["draft"] == 1
