"""Foundry lifecycle events (spine A4 — Track 2).

The model foundry emits its own observability events so the closed loop is
auditable: a dataset was built, a candidate was evaluated, a promotion was
requested, a candidate was promoted. These are OPERATIONAL / governance events
about the PIPELINE, not about a learner — they carry NO ``canonical_uuid`` and
NO PII. They are deliberately separate from the learner event contract
(contracts/src/events) because they describe the model factory, not learning.

Each event is an immutable record (frozen dataclass) with a stable ``type`` and
a server-shaped ``emitted_at``. A sink is injectable so a deployment can route
these to the AI fabric's observability / Langfuse without this module taking a
dependency on it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Literal
from uuid import UUID

FoundryEventType = Literal[
    "modelfoundry.dataset-built",
    "modelfoundry.candidate-evaluated",
    "modelfoundry.promotion-requested",
    "modelfoundry.promoted",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class FoundryEvent:
    """Immutable foundry event. PII-free; no learner identity is carried."""

    type: FoundryEventType
    emitted_at: datetime
    payload: dict


def dataset_built(
    *,
    dataset_id: str,
    content_hash: str,
    total_examples: int,
    split_counts: dict[str, int],
    per_class_counts: dict[str, int],
    consent_ref_count: int,
    emitted_at: datetime | None = None,
) -> FoundryEvent:
    """Emit that a versioned dataset was built. Carries the content hash for
    reproducibility and the COUNT of contributing consent refs (not the refs
    themselves in the wire payload by default)."""
    return FoundryEvent(
        type="modelfoundry.dataset-built",
        emitted_at=emitted_at or _now(),
        payload={
            "dataset_id": dataset_id,
            "content_hash": content_hash,
            "total_examples": total_examples,
            "split_counts": split_counts,
            "per_class_counts": per_class_counts,
            "consent_ref_count": consent_ref_count,
        },
    )


def candidate_evaluated(
    *,
    candidate_id: str,
    dataset_id: str,
    composite: float,
    candidate_better: bool,
    summary: str,
    emitted_at: datetime | None = None,
) -> FoundryEvent:
    """Emit a candidate's eval verdict (scorecard composite + head-to-head)."""
    return FoundryEvent(
        type="modelfoundry.candidate-evaluated",
        emitted_at=emitted_at or _now(),
        payload={
            "candidate_id": candidate_id,
            "dataset_id": dataset_id,
            "composite": composite,
            "candidate_better": candidate_better,
            "summary": summary,
        },
    )


def promotion_requested(
    *,
    candidate_id: str,
    requires_approval: bool,
    eligible: bool,
    rung: str,
    reason: str,
    emitted_at: datetime | None = None,
) -> FoundryEvent:
    """Emit a permission-ladder promotion request. ``requires_approval`` is
    always True for a consequential promotion (INVARIANT 8)."""
    return FoundryEvent(
        type="modelfoundry.promotion-requested",
        emitted_at=emitted_at or _now(),
        payload={
            "candidate_id": candidate_id,
            "requires_approval": requires_approval,
            "eligible": eligible,
            "rung": rung,
            "reason": reason,
        },
    )


def promoted(
    *,
    candidate_id: str,
    student_label: str,
    approved_by: UUID,
    approved_at: datetime,
    previous_active: str | None,
    emitted_at: datetime | None = None,
) -> FoundryEvent:
    """Emit that an APPROVED candidate advanced into the Track 2 slot. Records
    who/when (opaque approver ref — not PII)."""
    return FoundryEvent(
        type="modelfoundry.promoted",
        emitted_at=emitted_at or _now(),
        payload={
            "candidate_id": candidate_id,
            "student_label": student_label,
            "approved_by": str(approved_by),
            "approved_at": approved_at.isoformat(),
            "previous_active": previous_active,
            "track": 2,
        },
    )


# An event sink: anything that consumes a FoundryEvent (observability, audit).
EventSink = Callable[[FoundryEvent], None]


@dataclass
class CollectingSink:
    """A simple in-memory sink for tests / dev. Append-only."""

    events: list[FoundryEvent] = field(default_factory=list)

    def __call__(self, event: FoundryEvent) -> None:
        self.events.append(event)

    def types(self) -> list[str]:
        return [e.type for e in self.events]
