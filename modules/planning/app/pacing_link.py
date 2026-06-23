"""Pacing protection feed.

d6 emits pacing signals that the scheduling module (d-scheduling) consumes to
*protect* instructional pace: when a plan falls behind (rolled-over items piling
up) or races ahead (compression), this module produces a normalized
``PacingSignal`` the scheduler can act on (e.g. reclaim buffer blocks, defer
non-essential events) WITHOUT this module reaching into the scheduler's
internals.

Boundary contract
-----------------
* This module produces signals; it does NOT mutate timetables. Scheduling owns
  the calendar. We pass a ``deliver`` callable (the scheduling intake adapter)
  that is injected by the caller. If absent, signals are buffered locally and
  the feed degrades gracefully (no network/DB needed).
* Consequential timetable changes are advisory only here: a signal carries a
  recommended action but never auto-fires it. Human/scheduler approval applies
  downstream (permission ladder).
* Subjects are referenced by canonical_uuid only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Sequence, Tuple

from .events import EventLog, EventType


class PacingState(str, Enum):
    ON_TRACK = "on_track"
    BEHIND = "behind"
    AHEAD = "ahead"


class RecommendedAction(str, Enum):
    NONE = "none"
    PROTECT_BLOCK = "protect_block"      # ask scheduler to ring-fence time
    RECLAIM_BUFFER = "reclaim_buffer"    # pull from buffer to catch up
    RELEASE_BUFFER = "release_buffer"    # free time when ahead


@dataclass(frozen=True)
class PacingSignal:
    """A normalized, advisory pacing signal for the scheduler.

    ``deficit_minutes`` > 0 means behind by that many minutes; < 0 means ahead.
    ``recommended_action`` is advisory only; never auto-applied here.
    """

    subject_uuid: str
    state: PacingState
    deficit_minutes: int
    rolled_over_count: int
    recommended_action: RecommendedAction
    confidence: float = 1.0  # 0..1 from generate-and-verify gate
    note: str = ""

    def __post_init__(self) -> None:
        if not self.subject_uuid:
            raise ValueError("PacingSignal requires a canonical subject_uuid")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be within [0, 1]")


# Below this confidence the signal is held back from the scheduler and surfaced
# for human review instead (confidence gate).
DEFAULT_CONFIDENCE_GATE = 0.5


class PacingProtectionFeed:
    """Builds and routes pacing signals to scheduling.

    ``deliver`` is the scheduling-side intake adapter (injected). It receives a
    ``PacingSignal`` and is responsible for any consequential action subject to
    the scheduler's own approval rules. When ``deliver`` is None, signals are
    buffered so the feed remains usable with no live scheduler.
    """

    def __init__(
        self,
        deliver: Optional[Callable[[PacingSignal], None]] = None,
        event_log: Optional[EventLog] = None,
        confidence_gate: float = DEFAULT_CONFIDENCE_GATE,
        behind_threshold_minutes: int = 20,
        ahead_threshold_minutes: int = 20,
    ) -> None:
        self._deliver = deliver
        self._events = event_log
        self.confidence_gate = confidence_gate
        self.behind_threshold_minutes = behind_threshold_minutes
        self.ahead_threshold_minutes = ahead_threshold_minutes
        self._buffer: List[PacingSignal] = []
        self._held: List[PacingSignal] = []

    def assess(
        self,
        subject_uuid: str,
        planned_minutes: int,
        delivered_minutes: int,
        rolled_over_count: int,
        confidence: float = 1.0,
    ) -> PacingSignal:
        """Compute a pacing signal from planned vs delivered time.

        Positive deficit => behind. Negative => ahead.
        """
        if planned_minutes < 0 or delivered_minutes < 0:
            raise ValueError("minutes must be non-negative")
        deficit = planned_minutes - delivered_minutes

        if deficit >= self.behind_threshold_minutes or rolled_over_count > 0:
            state = PacingState.BEHIND
            action = (
                RecommendedAction.RECLAIM_BUFFER
                if deficit >= self.behind_threshold_minutes
                else RecommendedAction.PROTECT_BLOCK
            )
        elif -deficit >= self.ahead_threshold_minutes:
            state = PacingState.AHEAD
            action = RecommendedAction.RELEASE_BUFFER
        else:
            state = PacingState.ON_TRACK
            action = RecommendedAction.NONE

        return PacingSignal(
            subject_uuid=subject_uuid,
            state=state,
            deficit_minutes=deficit,
            rolled_over_count=rolled_over_count,
            recommended_action=action,
            confidence=confidence,
            note=f"{delivered_minutes}/{planned_minutes} min delivered",
        )

    def feed(self, signal: PacingSignal) -> bool:
        """Route a signal. Returns True if delivered/buffered, False if held.

        Signals below the confidence gate are held back for human review and are
        never auto-delivered to the scheduler (permission ladder + confidence
        gate).
        """
        if signal.confidence < self.confidence_gate:
            self._held.append(signal)
            self._emit(signal, delivered=False)
            return False

        if self._deliver is not None:
            self._deliver(signal)
        else:
            self._buffer.append(signal)
        self._emit(signal, delivered=True)
        return True

    def _emit(self, signal: PacingSignal, delivered: bool) -> None:
        if self._events is None:
            return
        self._events.emit(
            EventType.PACING_SIGNAL_EMITTED,
            subject_uuid=signal.subject_uuid,
            payload={
                "state": signal.state.value,
                "deficit_minutes": signal.deficit_minutes,
                "rolled_over_count": signal.rolled_over_count,
                "recommended_action": signal.recommended_action.value,
                "confidence": signal.confidence,
                "delivered_to_scheduler": delivered,
            },
        )

    @property
    def buffered(self) -> Tuple[PacingSignal, ...]:
        return tuple(self._buffer)

    @property
    def held(self) -> Tuple[PacingSignal, ...]:
        """Signals withheld pending human review (below confidence gate)."""
        return tuple(self._held)

    def assess_and_feed(
        self,
        subject_uuid: str,
        planned_minutes: int,
        delivered_minutes: int,
        rolled_over_count: int,
        confidence: float = 1.0,
    ) -> Tuple[PacingSignal, bool]:
        signal = self.assess(
            subject_uuid,
            planned_minutes,
            delivered_minutes,
            rolled_over_count,
            confidence,
        )
        return signal, self.feed(signal)
