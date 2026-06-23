"""The approval-workflow state machine.

A recommendation that needs a human decision moves through:

    PENDING --approve--> APPROVED
    PENDING --adjust---> ADJUSTED
    PENDING --decline--> DECLINED

These are terminal once recorded: a decision is never overwritten in place. The
ledger is append-only in intent — it records WHO decided and WHEN, and exposes
the full trail. (The durable, immutable audit lives in the event store / A7;
this in-memory ledger mirrors that contract for the runtime and tests.)

INVARIANT 8: only APPROVED or ADJUSTED clears an execute_with_permission action.
Agents hold no credentials and cannot self-approve — ``decided_by`` is the
opaque ref of a human, supplied by the caller after a real human gate.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from .models import ApprovalDecision, ApprovalDecisionKind, grants_execution


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    ADJUSTED = "adjusted"
    DECLINED = "declined"


#: Which terminal state each decision kind drives to.
_DECISION_TO_STATE: dict[str, ApprovalState] = {
    ApprovalDecisionKind.APPROVE.value: ApprovalState.APPROVED,
    ApprovalDecisionKind.ADJUST.value: ApprovalState.ADJUSTED,
    ApprovalDecisionKind.DECLINE.value: ApprovalState.DECLINED,
}

#: The states that authorise an execute_with_permission action to proceed.
_CLEARING_STATES: frozenset[ApprovalState] = frozenset(
    {ApprovalState.APPROVED, ApprovalState.ADJUSTED}
)


def state_for_decision(decision: ApprovalDecision) -> ApprovalState:
    """Map a recorded decision to its terminal approval state."""
    return _DECISION_TO_STATE[decision.decision]


def state_clears_execution(state: ApprovalState) -> bool:
    """True when this approval state authorises execution to proceed."""
    return state in _CLEARING_STATES


@dataclass(frozen=True)
class ApprovalRecord:
    """One entry in the immutable approval trail."""

    recommendation_id: UUID
    state: ApprovalState
    decision: ApprovalDecision | None  # None for the initial PENDING entry
    recorded_at: datetime

    @property
    def clears_execution(self) -> bool:
        return state_clears_execution(self.state)


class ApprovalLedger(ABC):
    """The append-only approval ledger interface.

    A recommendation is opened as PENDING, then a single human decision moves it
    to a terminal state. Recording a decision on a non-pending recommendation is
    refused — decisions are never silently overwritten.
    """

    @abstractmethod
    def open(self, recommendation_id: UUID, *, at: datetime | None = None) -> ApprovalRecord:
        """Open a recommendation as PENDING. Idempotent open is refused."""

    @abstractmethod
    def record_decision(self, decision: ApprovalDecision) -> ApprovalRecord:
        """Record a human decision, transitioning PENDING -> terminal."""

    @abstractmethod
    def current_state(self, recommendation_id: UUID) -> ApprovalState | None:
        """The current state, or None if the recommendation was never opened."""

    @abstractmethod
    def trail(self, recommendation_id: UUID) -> list[ApprovalRecord]:
        """The full, ordered trail for one recommendation."""

    @abstractmethod
    def is_cleared(self, recommendation_id: UUID) -> bool:
        """True when an execute_with_permission action is authorised to proceed."""


class InMemoryApprovalLedger(ApprovalLedger):
    """Thread-safe in-memory ledger.

    Append-only in intent: entries are appended and never mutated. The durable
    store of record is the event store (A7); this mirrors its transition
    contract for the runtime and tests.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._trails: dict[UUID, list[ApprovalRecord]] = {}

    @staticmethod
    def _now(at: datetime | None) -> datetime:
        return at or datetime.now(timezone.utc)

    def open(self, recommendation_id: UUID, *, at: datetime | None = None) -> ApprovalRecord:
        with self._lock:
            if recommendation_id in self._trails:
                raise ValueError(
                    f"Recommendation {recommendation_id} is already open; cannot reopen."
                )
            record = ApprovalRecord(
                recommendation_id=recommendation_id,
                state=ApprovalState.PENDING,
                decision=None,
                recorded_at=self._now(at),
            )
            self._trails[recommendation_id] = [record]
            return record

    def record_decision(self, decision: ApprovalDecision) -> ApprovalRecord:
        with self._lock:
            trail = self._trails.get(decision.recommendation_id)
            if trail is None:
                raise ValueError(
                    f"Recommendation {decision.recommendation_id} was never opened; "
                    "open it as PENDING before recording a decision."
                )
            current = trail[-1].state
            if current is not ApprovalState.PENDING:
                raise ValueError(
                    f"Recommendation {decision.recommendation_id} is already "
                    f"'{current.value}'; decisions are terminal and never overwritten."
                )
            new_state = state_for_decision(decision)
            record = ApprovalRecord(
                recommendation_id=decision.recommendation_id,
                state=new_state,
                decision=decision,
                recorded_at=decision.decided_at,
            )
            trail.append(record)
            return record

    def current_state(self, recommendation_id: UUID) -> ApprovalState | None:
        with self._lock:
            trail = self._trails.get(recommendation_id)
            return trail[-1].state if trail else None

    def trail(self, recommendation_id: UUID) -> list[ApprovalRecord]:
        with self._lock:
            return list(self._trails.get(recommendation_id, []))

    def is_cleared(self, recommendation_id: UUID) -> bool:
        with self._lock:
            trail = self._trails.get(recommendation_id)
            if not trail:
                return False
            last = trail[-1]
            return last.clears_execution and last.decision is not None and grants_execution(
                last.decision
            )
