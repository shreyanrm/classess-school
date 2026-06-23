"""Live session lifecycle (D7): join/presence, breakout rooms, class tools.

The live session is the runtime of a period launched from the timetable. This
module is the deterministic state engine for it:

  - Lifecycle: scheduled -> live -> ended. State transitions are explicit and
    one-way (a session never silently un-ends).
  - Presence: who has joined, their connection state, and (for online classes)
    whether a person is in front of the camera. The "no person in front of the
    camera" signal is ASSISTIVE only (see ``attention``) — it never marks a
    student absent and never grades anyone; attendance is the attendance engine's
    job and is always human-confirmed there.
  - Breakout rooms: automatic (balanced split, optionally mastery-aware via an
    injected grouping key) or manual. Rooms are reversible; closing a room
    returns everyone to the main room.
  - Class tools: stopwatch / timer and equitable random-selection that does not
    repeat a participant until the pool is exhausted.

PII discipline: a participant is an opaque ``participant_ref`` (the canonical
UUID). No names, no PII. Recording/transcription only run where consent permits
and a provider is wired (clss.classroom.dev.recording_bucket /
clss.classroom.dev.transcription_provider_key); with neither, those features are
simply unavailable, never faked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Iterable
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Lifecycle.
# ---------------------------------------------------------------------------
class SessionStatus(str, Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    ENDED = "ended"


class SessionMode(str, Enum):
    IN_PERSON = "in_person"
    ONLINE = "online"
    HYBRID = "hybrid"


class ConnectionState(str, Enum):
    JOINED = "joined"
    LEFT = "left"


# Camera-presence is an ASSISTIVE hint for online sessions only. It is NOT
# attendance and NOT a judgment about a person.
class CameraPresence(str, Enum):
    UNKNOWN = "unknown"        # no camera, off, or not reported
    PERSON_PRESENT = "person_present"
    NO_PERSON = "no_person"    # assistive nudge to the teacher; never punitive


@dataclass
class Participant:
    """A joined participant. ``participant_ref`` is the opaque canonical UUID."""

    participant_ref: UUID
    connection: ConnectionState = ConnectionState.JOINED
    is_host: bool = False
    room_id: UUID | None = None  # None = main room
    camera_presence: CameraPresence = CameraPresence.UNKNOWN
    joined_at: datetime = field(default_factory=_now)


@dataclass
class BreakoutRoom:
    room_id: UUID
    label: str
    open: bool = True


class LiveSessionError(RuntimeError):
    """Illegal lifecycle transition or operation."""


@dataclass
class LiveSession:
    """The live-session state engine. Pure in-memory; sync over the realtime
    channel when wired."""

    session_id: UUID
    mode: SessionMode
    status: SessionStatus = SessionStatus.SCHEDULED
    started_at: datetime | None = None
    ended_at: datetime | None = None
    _participants: dict[UUID, Participant] = field(default_factory=dict)
    _rooms: dict[UUID, BreakoutRoom] = field(default_factory=dict)
    _selection_pool: list[UUID] = field(default_factory=list)

    @classmethod
    def schedule(cls, mode: SessionMode, session_id: UUID | None = None) -> "LiveSession":
        return cls(session_id=session_id or uuid4(), mode=mode)

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> "LiveSession":
        if self.status is not SessionStatus.SCHEDULED:
            raise LiveSessionError(f"cannot start a session in status {self.status.value}")
        self.status = SessionStatus.LIVE
        self.started_at = _now()
        return self

    def end(self) -> "LiveSession":
        if self.status is not SessionStatus.LIVE:
            raise LiveSessionError(f"cannot end a session in status {self.status.value}")
        self.status = SessionStatus.ENDED
        self.ended_at = _now()
        # Close all breakout rooms; everyone returns to the main room.
        for p in self._participants.values():
            p.room_id = None
        for r in self._rooms.values():
            r.open = False
        return self

    @property
    def is_live(self) -> bool:
        return self.status is SessionStatus.LIVE

    # -- presence ----------------------------------------------------------
    def join(self, participant_ref: UUID, *, is_host: bool = False) -> Participant:
        if self.status is SessionStatus.ENDED:
            raise LiveSessionError("cannot join an ended session")
        existing = self._participants.get(participant_ref)
        if existing is not None:
            existing.connection = ConnectionState.JOINED
            return existing
        p = Participant(participant_ref=participant_ref, is_host=is_host)
        self._participants[participant_ref] = p
        return p

    def leave(self, participant_ref: UUID) -> None:
        p = self._participants.get(participant_ref)
        if p is not None:
            p.connection = ConnectionState.LEFT
            p.room_id = None

    def report_camera_presence(self, participant_ref: UUID, presence: CameraPresence) -> None:
        """Record an ASSISTIVE camera-presence hint (online sessions). This never
        changes attendance and never penalises anyone; it only feeds the teacher's
        engagement view via ``attention``."""
        p = self._participants.get(participant_ref)
        if p is None:
            raise LiveSessionError("unknown participant")
        p.camera_presence = presence

    @property
    def present(self) -> list[Participant]:
        """Currently-joined participants (opaque refs only)."""
        return [p for p in self._participants.values() if p.connection is ConnectionState.JOINED]

    @property
    def present_count(self) -> int:
        return len(self.present)

    def participant(self, participant_ref: UUID) -> Participant:
        return self._participants[participant_ref]

    # -- breakout rooms ----------------------------------------------------
    def open_rooms(self, labels: Iterable[str]) -> list[BreakoutRoom]:
        rooms = [BreakoutRoom(room_id=uuid4(), label=label) for label in labels]
        for r in rooms:
            self._rooms[r.room_id] = r
        return rooms

    def assign(self, participant_ref: UUID, room_id: UUID | None) -> None:
        """Move a participant to a room (or back to the main room with None)."""
        p = self._participants.get(participant_ref)
        if p is None:
            raise LiveSessionError("unknown participant")
        if room_id is not None:
            room = self._rooms.get(room_id)
            if room is None or not room.open:
                raise LiveSessionError("room is not open")
        p.room_id = room_id

    def auto_breakout(
        self,
        count: int,
        *,
        grouping_key: Callable[[UUID], float] | None = None,
    ) -> list[BreakoutRoom]:
        """Split the present participants into ``count`` balanced rooms.

        When ``grouping_key`` is supplied (e.g. a mastery score), participants are
        sorted by it and dealt round-robin so each room is balanced across the key
        rather than clustered — mastery-aware composition over the data, not a
        random shuffle. Deterministic given the inputs.
        """
        if count < 1:
            raise LiveSessionError("need at least one room")
        present = self.present
        if not present:
            return []
        rooms = self.open_rooms([f"Room {i + 1}" for i in range(count)])
        refs = [p.participant_ref for p in present]
        if grouping_key is not None:
            refs.sort(key=grouping_key)
        else:
            # Stable, deterministic order by ref so the split is reproducible.
            refs.sort(key=lambda r: r.int)
        for i, ref in enumerate(refs):
            self.assign(ref, rooms[i % count].room_id)
        return rooms

    def close_rooms(self) -> None:
        """Close all breakout rooms; everyone returns to the main room."""
        for p in self._participants.values():
            p.room_id = None
        for r in self._rooms.values():
            r.open = False

    def room_members(self, room_id: UUID | None) -> list[Participant]:
        return [p for p in self.present if p.room_id == room_id]

    # -- equitable random selection ---------------------------------------
    def pick_random(self, rng: Callable[[int], int] | None = None) -> UUID | None:
        """Equitable random selection: never repeats a participant until the whole
        present pool has been picked once, then the pool refills.

        ``rng`` is an injectable ``randbelow``-style function (n -> [0,n)) so the
        choice is deterministic in tests. Defaults to ``secrets.randbelow``.
        """
        present_refs = [p.participant_ref for p in self.present]
        if not present_refs:
            return None
        # Drop anyone who has left from the remaining pool, and refill if drained.
        self._selection_pool = [r for r in self._selection_pool if r in set(present_refs)]
        if not self._selection_pool:
            self._selection_pool = list(present_refs)
        if rng is None:
            import secrets

            rng = secrets.randbelow
        idx = rng(len(self._selection_pool))
        chosen = self._selection_pool.pop(idx)
        return chosen


# ---------------------------------------------------------------------------
# Class timing tools — stopwatch + countdown timer (deterministic via clock).
# ---------------------------------------------------------------------------
@dataclass
class Stopwatch:
    """A monotonic stopwatch. ``clock`` returns epoch seconds; injectable for
    deterministic tests."""

    clock: Callable[[], float]
    _start: float | None = None
    _accumulated: float = 0.0
    running: bool = False

    def start(self) -> None:
        if not self.running:
            self._start = self.clock()
            self.running = True

    def stop(self) -> None:
        if self.running and self._start is not None:
            self._accumulated += self.clock() - self._start
            self._start = None
            self.running = False

    def reset(self) -> None:
        self._start = None
        self._accumulated = 0.0
        self.running = False

    @property
    def elapsed(self) -> float:
        if self.running and self._start is not None:
            return self._accumulated + (self.clock() - self._start)
        return self._accumulated


@dataclass
class Timer:
    """A countdown timer over an injectable clock."""

    duration_s: float
    clock: Callable[[], float]
    _start: float | None = None

    def start(self) -> None:
        self._start = self.clock()

    @property
    def remaining(self) -> float:
        if self._start is None:
            return self.duration_s
        return max(0.0, self.duration_s - (self.clock() - self._start))

    @property
    def expired(self) -> bool:
        return self._start is not None and self.remaining <= 0.0
