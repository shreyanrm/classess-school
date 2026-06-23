"""Live session: join/presence, breakout rooms, permission-laddered close."""

from __future__ import annotations

import pytest

from app import events
from app.live import (
    LiveSession,
    Participant,
    SessionState,
)


def _uuid() -> str:
    return events.new_canonical_uuid()


def test_open_then_join_tracks_presence():
    s = LiveSession()
    s.open()
    assert s.state is SessionState.LIVE
    u = _uuid()
    s.join(Participant(subject_uuid=u, role="learner"))
    assert u in s.present_uuids
    assert s.present_count() == 1


def test_participant_requires_opaque_uuid():
    with pytest.raises(ValueError):
        Participant(subject_uuid="Asha Rao")


def test_leave_updates_presence():
    s = LiveSession()
    s.open()
    u = _uuid()
    s.join(Participant(subject_uuid=u))
    s.leave(u)
    assert u not in s.present_uuids
    assert s.present_count() == 0


def test_close_requires_human_approval_permission_ladder():
    s = LiveSession()
    s.open()
    s.request_close(_uuid())
    assert s.state is SessionState.CLOSING  # staged, not closed
    # close did NOT auto-fire
    assert s.state is not SessionState.CLOSED
    ev = s.approve_close(_uuid())
    assert s.state is SessionState.CLOSED
    assert ev.payload["human_approved"] is True


def test_cannot_approve_close_without_request():
    s = LiveSession()
    s.open()
    with pytest.raises(RuntimeError):
        s.approve_close(_uuid())


def test_breakout_only_includes_present_participants():
    s = LiveSession()
    s.open()
    a, b = _uuid(), _uuid()
    s.join(Participant(subject_uuid=a))
    s.join(Participant(subject_uuid=b))
    room, ev = s.open_breakout("Group 1", [a, b])
    assert ev.kind == events.EventKind.BREAKOUT_OPENED
    assert room.member_uuids == frozenset({a, b})
    assert len(s.rooms) == 1


def test_breakout_rejects_absent_member():
    s = LiveSession()
    s.open()
    a = _uuid()
    s.join(Participant(subject_uuid=a))
    with pytest.raises(ValueError):
        s.open_breakout("Group X", [a, _uuid()])  # second never joined


def test_close_breakout_removes_room():
    s = LiveSession()
    s.open()
    a = _uuid()
    s.join(Participant(subject_uuid=a))
    room, _ = s.open_breakout("G", [a])
    s.close_breakout(room.room_id)
    assert len(s.rooms) == 0


def test_roster_export_is_consent_gated():
    s = LiveSession()
    s.open()
    s.join(Participant(subject_uuid=_uuid()))
    assert s.export_roster(consent_granted=False) == ()
    assert len(s.export_roster(consent_granted=True)) == 1


def test_join_event_carries_opaque_uuid_only():
    s = LiveSession()
    s.open()
    u = _uuid()
    ev = s.join(Participant(subject_uuid=u, role="learner"))
    assert ev.subject_uuid == u
    assert "name" not in ev.payload and "email" not in ev.payload
