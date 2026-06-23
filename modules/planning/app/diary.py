"""The teacher diary (d6) — planned vs delivered, auto-updated.

An automatic teacher diary records what was actually taught versus what was
planned. Each planned item starts as a PLANNED entry; as delivery signals arrive
from the classroom-delivery surface the entry is reconciled to DELIVERED (taught
in full), PARTIAL (taught short of the planned time), and items never delivered
remain PLANNED and surface as gaps.

Every entry maps to the ontology by opaque outcome ids and carries no PII
(INVARIANT 1 + 2): the diary is the teacher's record of curriculum delivery, not
a record about any child. It feeds pacing protection (delivered-minute count) and
the planned-vs-delivered evidence a coordinator reads.

Pure, deterministic, dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence

from .events import EventLog, EventType


class DeliveryStatus(str, Enum):
    """Where a planned item sits against delivery."""

    PLANNED = "planned"        # planned, not yet delivered (a gap until delivered)
    DELIVERED = "delivered"    # delivered in full (>= planned minutes)
    PARTIAL = "partial"        # delivered, but short of the planned minutes


@dataclass
class DiaryEntry:
    """One planned-vs-delivered line, mapped to the ontology. No PII — only an
    opaque item id and opaque outcome ids."""

    item_id: str
    outcome_ids: tuple[str, ...]
    planned_minutes: int
    delivered_minutes: int = 0
    status: DeliveryStatus = DeliveryStatus.PLANNED
    note: str = ""

    @property
    def is_gap(self) -> bool:
        """A planned item with no delivery is an undelivered gap."""
        return self.status == DeliveryStatus.PLANNED

    @property
    def outcome_coverage(self) -> float:
        """Fraction of planned time delivered, clamped to [0,1]."""
        if self.planned_minutes <= 0:
            return 1.0 if self.delivered_minutes > 0 else 0.0
        return round(min(self.delivered_minutes / self.planned_minutes, 1.0), 4)


class TeacherDiary:
    """The reconciled diary for one owner+subject: planned vs delivered.

    The diary is auto-updated by signals, never hand-authored line by line:
    :meth:`plan_item` records intent; :meth:`record_delivery` reconciles a
    delivery signal against it. An optional event log captures planned/delivered/
    partial events on the append-only spine.
    """

    def __init__(
        self,
        owner_uuid: str,
        subject_uuid: str,
        event_log: Optional[EventLog] = None,
    ) -> None:
        if not owner_uuid:
            raise ValueError("TeacherDiary requires an owner_uuid (opaque token).")
        if not subject_uuid:
            raise ValueError("TeacherDiary requires a subject_uuid (opaque token).")
        self.owner_uuid = owner_uuid
        self.subject_uuid = subject_uuid
        self._events = event_log
        self._entries: Dict[str, DiaryEntry] = {}
        self._order: List[str] = []

    # -- authoring intent --------------------------------------------------

    def plan_item(
        self,
        item_id: str,
        *,
        outcome_ids: Sequence[str],
        planned_minutes: int,
    ) -> DiaryEntry:
        """Record a planned item as a PLANNED diary entry."""
        if not item_id:
            raise ValueError("plan_item requires an item_id.")
        if planned_minutes < 0:
            raise ValueError("planned_minutes must be non-negative.")
        entry = DiaryEntry(
            item_id=item_id,
            outcome_ids=tuple(outcome_ids),
            planned_minutes=planned_minutes,
            delivered_minutes=0,
            status=DeliveryStatus.PLANNED,
        )
        if item_id not in self._entries:
            self._order.append(item_id)
        self._entries[item_id] = entry
        self._emit(
            EventType.DIARY_PLANNED,
            {
                "item_id": item_id,
                "planned_minutes": planned_minutes,
                "outcome_ids": list(entry.outcome_ids),
            },
        )
        return entry

    # -- reconciling delivery ----------------------------------------------

    def record_delivery(self, item_id: str, *, delivered_minutes: int) -> DiaryEntry:
        """Reconcile a delivery signal against a planned item.

        Delivered in full (>= planned) -> DELIVERED; delivered short -> PARTIAL.
        Recording delivery for an unknown item is an error — the diary only
        tracks planned items (off-plan teaching is recorded by planning the item
        first)."""
        if item_id not in self._entries:
            raise KeyError(f"no planned diary entry for item {item_id!r}")
        if delivered_minutes < 0:
            raise ValueError("delivered_minutes must be non-negative.")
        entry = self._entries[item_id]
        entry.delivered_minutes = delivered_minutes
        if delivered_minutes >= entry.planned_minutes and delivered_minutes > 0:
            entry.status = DeliveryStatus.DELIVERED
            self._emit(
                EventType.DIARY_DELIVERED,
                {"item_id": item_id, "delivered_minutes": delivered_minutes},
            )
        elif delivered_minutes > 0:
            entry.status = DeliveryStatus.PARTIAL
            self._emit(
                EventType.DIARY_PARTIAL,
                {
                    "item_id": item_id,
                    "delivered_minutes": delivered_minutes,
                    "planned_minutes": entry.planned_minutes,
                },
            )
        else:
            entry.status = DeliveryStatus.PLANNED
        return entry

    # -- reads -------------------------------------------------------------

    def entry(self, item_id: str) -> DiaryEntry:
        return self._entries[item_id]

    @property
    def entries(self) -> tuple[DiaryEntry, ...]:
        return tuple(self._entries[i] for i in self._order)

    def undelivered(self) -> tuple[DiaryEntry, ...]:
        """Planned items that have not been delivered — the gaps."""
        return tuple(
            self._entries[i]
            for i in self._order
            if self._entries[i].status == DeliveryStatus.PLANNED
        )

    def planned_vs_delivered(self) -> Dict[str, object]:
        """Roll-up of planned vs delivered minutes and per-status counts."""
        planned_minutes = sum(e.planned_minutes for e in self.entries)
        delivered_minutes = sum(e.delivered_minutes for e in self.entries)
        delivered_count = sum(
            1 for e in self.entries if e.status == DeliveryStatus.DELIVERED
        )
        partial_count = sum(
            1 for e in self.entries if e.status == DeliveryStatus.PARTIAL
        )
        planned_count = sum(
            1 for e in self.entries if e.status == DeliveryStatus.PLANNED
        )
        return {
            "planned_minutes": planned_minutes,
            "delivered_minutes": delivered_minutes,
            "delivered_count": delivered_count,
            "partial_count": partial_count,
            "planned_count": planned_count,
        }

    # -- internals ---------------------------------------------------------

    def _emit(self, event_type: EventType, payload: Dict[str, object]) -> None:
        if self._events is None:
            return
        self._events.emit(event_type, subject_uuid=self.subject_uuid, payload=payload)
