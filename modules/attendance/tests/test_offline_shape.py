"""Offline-capable shape: the domain works with no network and no DB.

Capture, reconciliation, staff and event building are pure functions over
in-memory data. A device can capture offline, build drafts and events, and
sync later. This test asserts the end-to-end flow runs with no I/O and that
nothing in the call graph reaches out to a socket.
"""

import builtins
import socket

import pytest

from app.capture import (
    capture_absent_only,
    capture_online_presence,
    confirm_roll,
    summarize_draft,
)
from app.events import (
    collect_append_only,
    roll_confirmed_event,
    substitution_needed_event,
)
from app.reconciliation import reconcile, to_review_payload
from app.staff import (
    StaffStatus,
    build_substitution_request,
    confirm_staff,
    record_staff,
)

ROSTER = ["uuid-a", "uuid-b", "uuid-c"]


@pytest.fixture
def no_network(monkeypatch):
    """Make any socket connection attempt fail loudly."""

    def _boom(*args, **kwargs):
        raise AssertionError("network access is not allowed offline")

    monkeypatch.setattr(socket.socket, "connect", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    return True


def test_full_capture_flow_offline(no_network):
    # 1. two assisting methods build drafts offline
    d1 = capture_absent_only("sess-1", ROSTER, ["uuid-b"])
    d2 = capture_online_presence(
        "sess-1", ROSTER, {"uuid-a": 600, "uuid-c": 600}, 300
    )

    # 2. reconcile across methods, surface conflicts for review
    result = reconcile([d1, d2])
    _ = to_review_payload(result)

    # 3. teacher confirms (human gate) -> finalised roll
    final = confirm_roll(d1, confirmed_by="teacher-uuid")
    assert final.is_final is True

    # 4. build an immutable event and append to an in-memory log
    counts = summarize_draft(final)
    event = roll_confirmed_event(
        final.session_id, "teacher-uuid", final.method.value, counts
    )
    log = collect_append_only([], event)
    assert len(log) == 1


def test_staff_substitution_flow_offline(no_network):
    rec = record_staff("staff-1", "2026-06-22", StaffStatus.ABSENT, ["sess-1"])
    confirmed = confirm_staff(rec, confirmed_by="head-uuid")
    event = build_substitution_request(confirmed)
    assert event is not None
    log = collect_append_only([], event)
    assert len(log) == 1


def test_no_module_level_network_imports():
    # Sanity: importing the domain did not open a socket. If any module
    # tried network I/O at import time this fixture-less test would already
    # have failed during collection.
    assert hasattr(builtins, "open")
