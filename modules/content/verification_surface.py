"""The human verification / approval surface (B3).

The CONFIDENCE-BANDED REVIEW QUEUE. Generated and ingested content is prepared,
never auto-published (INVARIANT 8 — the permission ladder). This module holds
the data shapes a human reviewer works through and the queue that drives the
DRAFT -> IN_REVIEW -> APPROVED/REJECTED transitions on the repository.

Confidence banding (presentation only — never a substitute for the gate):

  - GREEN  — passed the gate cleanly (served, high confidence). Quick confirm.
  - AMBER  — served but near the threshold, or a soft signal needs a human eye.
  - RED    — withheld by the gate (deterministic failure, second-model
             disagreement, or below threshold) or never verified (ingested).
             A human must read it before anything is served.

The band is a triage hint for the reviewer's attention. It NEVER promotes
content on its own: only an explicit human ``ReviewDecision`` of APPROVE moves a
record to APPROVED, and the repository still refuses to make an unverified
version live (INVARIANT 7). A single item is never auto-confirmed.

The reviewer is identified by a generic role label (e.g. "reviewer:hod"), never
a real personal name. No emoji, no exclamation marks (product-copy law).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Sequence

from .repository import (
    ApprovalState,
    ApprovalTransitionError,
    ContentRecord,
    InMemoryContentRepository,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Confidence banding
# ---------------------------------------------------------------------------

class ConfidenceBand(str, Enum):
    """A triage band for reviewer attention. Presentation, not a gate."""

    GREEN = "green"   # gate passed cleanly; quick confirm
    AMBER = "amber"   # served but near threshold; a human eye is warranted
    RED = "red"       # withheld or never verified; a human must read it


# The amber margin above the gate threshold. Served content whose confidence is
# within this margin of the threshold is amber rather than green.
AMBER_MARGIN = 0.10


def band_for_confidence(
    *,
    served: bool,
    confidence: float,
    gate_threshold: float,
    verified: bool = True,
) -> ConfidenceBand:
    """Compute the triage band.

    ``served`` is the gate's verdict; ``verified`` is False for ingested content
    that never ran through the gate. Anything not served-and-verified is RED.
    """
    if not verified or not served:
        return ConfidenceBand.RED
    if confidence < gate_threshold:  # defensive — should not happen when served
        return ConfidenceBand.RED
    if confidence < gate_threshold + AMBER_MARGIN:
        return ConfidenceBand.AMBER
    return ConfidenceBand.GREEN


# ---------------------------------------------------------------------------
# Review verdict / decision
# ---------------------------------------------------------------------------

class ReviewVerdict(str, Enum):
    """A reviewer's explicit decision on a queued item."""

    APPROVE = "approve"   # publish this version to learners
    REJECT = "reject"     # do not publish; send back as rejected
    REVISE = "revise"     # send back to draft for changes
    DEFER = "defer"       # leave in review (no state change)


@dataclass(frozen=True)
class ReviewDecision:
    """An explicit human decision. This is the permission-ladder approval act.

    ``reviewer`` is a generic role label, never a real name. ``note`` is plain
    professional prose. There is no machine path that constructs an APPROVE
    decision on a human's behalf.
    """

    item_id: str
    verdict: ReviewVerdict
    reviewer: str
    version_id: str | None = None  # which version to publish on APPROVE (default: latest)
    note: str | None = None
    decided_at: datetime = field(default_factory=_now)


# ---------------------------------------------------------------------------
# Review item
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewItem:
    """One entry in the confidence-banded review queue.

    A snapshot of what the reviewer needs: the content under review, its band,
    the verification summary that produced the band, and the reason (if any) the
    gate withheld it. Immutable; resolved by recording a ``ReviewDecision``.
    """

    item_id: str
    content_id: str
    topic_id: str
    title: str
    band: ConfidenceBand
    served_by_gate: bool
    verified: bool
    confidence: float
    gate_threshold: float
    review_reason: str | None
    queued_at: datetime
    version_id: str | None = None
    resolved: bool = False
    decision: ReviewDecision | None = None


# ---------------------------------------------------------------------------
# The review queue
# ---------------------------------------------------------------------------

class ReviewQueue:
    """The confidence-banded human review queue over a content repository.

    Enqueues prepared content for human approval; applying an APPROVE decision
    is the explicit human act that promotes a record to APPROVED (the repository
    still refuses to publish an unverified version). RED items are surfaced first
    so the riskiest content gets the most human attention.
    """

    def __init__(self, repository: InMemoryContentRepository) -> None:
        self.repository = repository
        self._items: dict[str, ReviewItem] = {}

    # -- enqueue -----------------------------------------------------------

    def enqueue(
        self,
        content_id: str,
        *,
        served_by_gate: bool,
        verified: bool,
        confidence: float,
        gate_threshold: float,
        review_reason: str | None = None,
        version_id: str | None = None,
    ) -> ReviewItem:
        """Queue a content record for human review and move it to IN_REVIEW."""
        record = self.repository.require(content_id)
        if record.approval_state is ApprovalState.DRAFT:
            # Submitting for review is a safe, non-consequential transition.
            record = self.repository.transition(content_id, ApprovalState.IN_REVIEW)

        band = band_for_confidence(
            served=served_by_gate,
            confidence=confidence,
            gate_threshold=gate_threshold,
            verified=verified,
        )
        item = ReviewItem(
            item_id=_new_id(),
            content_id=content_id,
            topic_id=record.topic_id,
            title=record.title,
            band=band,
            served_by_gate=served_by_gate,
            verified=verified,
            confidence=confidence,
            gate_threshold=gate_threshold,
            review_reason=review_reason,
            queued_at=_now(),
            version_id=version_id or (record.latest_version.version_id if record.latest_version else None),
        )
        self._items[item.item_id] = item
        return item

    # -- read --------------------------------------------------------------

    def get(self, item_id: str) -> ReviewItem | None:
        return self._items.get(item_id)

    def pending(self) -> list[ReviewItem]:
        """Unresolved items, RED first then AMBER then GREEN, oldest first within a band."""
        order = {ConfidenceBand.RED: 0, ConfidenceBand.AMBER: 1, ConfidenceBand.GREEN: 2}
        items = [i for i in self._items.values() if not i.resolved]
        items.sort(key=lambda i: (order[i.band], i.queued_at, i.item_id))
        return items

    def by_band(self, band: ConfidenceBand) -> list[ReviewItem]:
        return [i for i in self.pending() if i.band is band]

    # -- decide ------------------------------------------------------------

    def decide(self, decision: ReviewDecision) -> ReviewItem:
        """Apply an explicit human decision.

        APPROVE promotes the record to APPROVED and makes the chosen version
        live — but the repository refuses if that version is not verified, so an
        approval can never serve unverified content (INVARIANT 7). REJECT and
        REVISE move the record out of review; DEFER leaves it queued.
        """
        item = self._items.get(decision.item_id)
        if item is None:
            raise KeyError(f"unknown review item: {decision.item_id!r}")
        if item.resolved:
            raise ValueError(f"review item {decision.item_id!r} is already resolved.")

        if decision.verdict is ReviewVerdict.DEFER:
            # No state change; record the decision but keep it pending.
            return item

        target_version = decision.version_id or item.version_id
        if decision.verdict is ReviewVerdict.APPROVE:
            # The repository enforces verified_served before promoting to live.
            self.repository.transition(
                item.content_id, ApprovalState.APPROVED, version_id=target_version
            )
        elif decision.verdict is ReviewVerdict.REJECT:
            self.repository.transition(item.content_id, ApprovalState.REJECTED)
        elif decision.verdict is ReviewVerdict.REVISE:
            self.repository.transition(item.content_id, ApprovalState.DRAFT)

        resolved = ReviewItem(
            **{**item.__dict__, "resolved": True, "decision": decision}
        )
        self._items[item.item_id] = resolved
        return resolved
