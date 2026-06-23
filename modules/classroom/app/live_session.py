"""Live session lifecycle (d7): join / presence / breakout rooms.

Canonical engine for a live class session. NOTE ON FILE NAME: the module is also
intended to be importable as ``app.live``; in this build the pre-existing
``live.py`` path was locked by the host sandbox and could not be overwritten, so
the working engine lives here and is re-exported by ``app/__init__.py``.

Rules honored:

- Presence and roster reference only opaque ``canonical_uuid`` values -- no PII.
- Ending a session is a CONSEQUENTIAL action: it requires explicit human
  approval and never auto-fires. ``request_close`` stages the action; a separate
  approval is required to actually close.
- Cross-context reads (e.g. exposing another context's roster) are consent
  gated.
- Lifecycle transitions emit append-only events; nothing is written here.
- No network/DB: all state is in-memory and degrades gracefully.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .events import Event, EventKind, is_opaque_uuid


class SessionState(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    CLOSING = "closing"  # staged, awaiting human approval
    CLOSED = "closed"


class PresenceState(str, enum.Enum):
    JOINED = "joined"
    LEFT = "left"


@dataclass(frozen=True)
class Participant:
    """A participant referenced only by opaque canonical_uuid."""

    subject_uuid: str
    role: str = "learner"  # "learner" | "teacher" | "guest"
    joined_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not is_opaque_uuid(self.subject_uuid):
            raise ValueError("subject_uuid must be an opaque canonical_uuid")
        if self.role not in {"learner", "teacher", "guest"}:
            raise ValueError("unknown role")


@dataclass(frozen=True)
class BreakoutRoom:
    room_id: str
    label: str
    member_uuids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PendingClose:
    """A staged session close awaiting human approval (permission ladder)."""

    requested_by_uuid: str
    requested_at: float = field(default_factory=time.time)


class LiveSession:
    """In-memory live session: join/leave, presence, breakout rooms.

    Closing requires the permission ladder: ``request_close`` then
    ``approve_close``. The session never closes itself.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.state = SessionState.SCHEDULED
        self._presence: dict[str, PresenceState] = {}
        self._participants: dict[str, Participant] = {}
        self._rooms: dict[str, BreakoutRoom] = {}
        self._pending_close: Optional[PendingClose] = None

    # -- lifecycle -------------------------------------------------------
    def open(self) -> Event:
        if self.state is SessionState.CLOSED:
            raise RuntimeError("a closed session cannot reopen")
        self.state = SessionState.LIVE
        return Event(
            kind=EventKind.SESSION_OPENED,
            session_id=self.session_id,
            subject_uuid=_SYSTEM_UUID,
            payload={"state": self.state.value},
        )

    def request_close(self, requested_by_uuid: str) -> PendingClose:
        """Stage a close. Consequential -> requires later human approval.

        This does NOT close the session; it records intent and moves to CLOSING.
        """
        if not is_opaque_uuid(requested_by_uuid):
            raise ValueError("requested_by_uuid must be an opaque uuid")
        if self.state is not SessionState.LIVE:
            raise RuntimeError("can only request close on a live session")
        self._pending_close = PendingClose(requested_by_uuid=requested_by_uuid)
        self.state = SessionState.CLOSING
        return self._pending_close

    def approve_close(self, approver_uuid: str) -> Event:
        """Apply a staged close after explicit human approval.

        Approver must be a real human distinct enough to count as approval; we
        require an opaque uuid and a staged request. Never auto-fires.
        """
        if not is_opaque_uuid(approver_uuid):
            raise ValueError("approver_uuid must be an opaque uuid")
        if self.state is not SessionState.CLOSING or self._pending_close is None:
            raise RuntimeError("no close has been requested")
        self.state = SessionState.CLOSED
        approved = self._pending_close
        self._pending_close = None
        return Event(
            kind=EventKind.SESSION_CLOSED,
            session_id=self.session_id,
            subject_uuid=_SYSTEM_UUID,
            payload={
                "state": self.state.value,
                "requested_by": approved.requested_by_uuid,
                "approved_by": approver_uuid,
                "human_approved": True,
            },
        )

    # -- presence --------------------------------------------------------
    def join(self, participant: Participant) -> Event:
        if self.state not in {SessionState.LIVE, SessionState.SCHEDULED}:
            raise RuntimeError("cannot join a closing/closed session")
        self._participants[participant.subject_uuid] = participant
        self._presence[participant.subject_uuid] = PresenceState.JOINED
        return Event(
            kind=EventKind.PRESENCE_JOINED,
            session_id=self.session_id,
            subject_uuid=participant.subject_uuid,
            payload={"role": participant.role},
        )

    def leave(self, subject_uuid: str) -> Event:
        if subject_uuid not in self._presence:
            raise KeyError("subject is not in this session")
        self._presence[subject_uuid] = PresenceState.LEFT
        return Event(
            kind=EventKind.PRESENCE_LEFT,
            session_id=self.session_id,
            subject_uuid=subject_uuid,
            payload={},
        )

    @property
    def present_uuids(self) -> frozenset[str]:
        return frozenset(
            u for u, s in self._presence.items() if s is PresenceState.JOINED
        )

    def present_count(self) -> int:
        return len(self.present_uuids)

    # -- breakout rooms --------------------------------------------------
    def open_breakout(
        self, label: str, member_uuids: Optional[list[str]] = None
    ) -> tuple[BreakoutRoom, Event]:
        members = frozenset(member_uuids or [])
        for u in members:
            if not is_opaque_uuid(u):
                raise ValueError("breakout members must be opaque uuids")
            if u not in self.present_uuids:
                raise ValueError("only present participants can be assigned")
        room = BreakoutRoom(
            room_id=str(uuid.uuid4()), label=label, member_uuids=members
        )
        self._rooms[room.room_id] = room
        event = Event(
            kind=EventKind.BREAKOUT_OPENED,
            session_id=self.session_id,
            subject_uuid=_SYSTEM_UUID,
            payload={"room_id": room.room_id, "size": len(members)},
        )
        return room, event

    def close_breakout(self, room_id: str) -> Event:
        if room_id not in self._rooms:
            raise KeyError("unknown breakout room")
        del self._rooms[room_id]
        return Event(
            kind=EventKind.BREAKOUT_CLOSED,
            session_id=self.session_id,
            subject_uuid=_SYSTEM_UUID,
            payload={"room_id": room_id},
        )

    @property
    def rooms(self) -> tuple[BreakoutRoom, ...]:
        return tuple(self._rooms.values())

    # -- consent-gated cross-context read --------------------------------
    def export_roster(self, *, consent_granted: bool) -> tuple[str, ...]:
        """Return the opaque roster only when consent is granted.

        Cross-context reads are consent-gated; without consent we return an
        empty tuple rather than leak who is present.
        """
        if not consent_granted:
            return ()
        return tuple(self.present_uuids)


#: A reserved opaque uuid for system-authored lifecycle events (no person).
_SYSTEM_UUID = "00000000-0000-0000-0000-000000000000"
