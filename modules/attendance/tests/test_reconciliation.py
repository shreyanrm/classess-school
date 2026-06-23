"""Reconciliation flags conflicts across methods for human review."""

import pytest

from app.capture import (
    capture_absent_only,
    capture_online_presence,
    capture_photo_roster,
)
from app.capture import Status
from app.reconciliation import (
    MethodSignal,
    Method,
    reconcile,
    reconcile_student,
    to_review_payload,
)

ROSTER = ["uuid-a", "uuid-b", "uuid-c"]


def test_agreement_no_conflict():
    d1 = capture_absent_only("s", ROSTER, ["uuid-b"])
    d2 = capture_online_presence(
        "s", ROSTER, {"uuid-a": 600, "uuid-c": 600}, 300
    )
    result = reconcile([d1, d2])
    # uuid-a present in both -> agreed
    a = next(m for m in result.marks if m.canonical_uuid == "uuid-a")
    assert a.conflict is False
    assert a.resolved_status is Status.PRESENT


def test_present_vs_absent_is_conflict():
    # absent-only says uuid-a present; photo-roster did not detect uuid-a
    # so it suggests absent -> material conflict.
    d1 = capture_absent_only("s", ROSTER, [])  # everyone present
    d2 = capture_photo_roster("s", ROSTER, {"uuid-b": 0.9, "uuid-c": 0.9})
    result = reconcile([d1, d2])
    a = next(m for m in result.marks if m.canonical_uuid == "uuid-a")
    assert a.conflict is True
    assert a.resolved_status is Status.UNKNOWN
    assert a.needs_review is True


def test_conflicts_collected_for_review():
    d1 = capture_absent_only("s", ROSTER, [])
    d2 = capture_photo_roster("s", ROSTER, {"uuid-b": 0.9})
    result = reconcile([d1, d2])
    payload = to_review_payload(result)
    assert payload
    for entry in payload:
        assert entry["needs_human_review"] is True
        assert "@" not in entry["canonical_uuid"]
        assert len(entry["methods"]) >= 2


def test_reconcile_requires_same_session():
    d1 = capture_absent_only("s1", ROSTER, [])
    d2 = capture_absent_only("s2", ROSTER, [])
    with pytest.raises(ValueError):
        reconcile([d1, d2])


def test_reconcile_empty_raises():
    with pytest.raises(ValueError):
        reconcile([])


def test_reconcile_student_soft_disagreement_needs_review():
    signals = [
        MethodSignal(Method.VOICE, Status.PRESENT, 0.9),
        MethodSignal(Method.ONLINE_PRESENCE, Status.LATE, 0.6),
    ]
    mark = reconcile_student("uuid-a", signals)
    # present vs late is not a material conflict but needs review
    assert mark.conflict is False
    assert mark.needs_review is True


def test_summary_counts():
    d1 = capture_absent_only("s", ROSTER, [])
    d2 = capture_photo_roster("s", ROSTER, {"uuid-b": 0.9})
    result = reconcile([d1, d2])
    summary = result.summary()
    assert summary["students"] == 3
    assert summary["conflicts"] >= 1
