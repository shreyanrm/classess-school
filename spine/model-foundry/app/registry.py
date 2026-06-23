"""Model registry / versioning + permission-laddered promotion (spine A4 — Track 2).

The registry tracks every candidate, its eval scorecard, and its lifecycle:
``registered -> evaluated -> promotion_requested -> (approved) promoted`` into
the Track 2 serving slot.

INVARIANT 8 — THE PERMISSION LADDER. Promoting a model to SERVE learners is
CONSEQUENTIAL. :meth:`request_promotion` returns a ``requires_approval``
decision; it NEVER advances a version into the serving slot on its own. Only
:meth:`approve_promotion`, given an explicit human approver, advances the
candidate. There is no auto-promote path anywhere in this module.

INVARIANT 11 — only Track 2 candidates can be promoted; the serving slot is
Track 2's. The record of who/when is IMMUTABLE once written (append-only history;
the active pointer moves but the history is never rewritten).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from .eval import Comparison, GateResult, Scorecard

TRACK_ID = 2


class CandidateState(str, Enum):
    REGISTERED = "registered"
    EVALUATED = "evaluated"
    PROMOTION_REQUESTED = "promotion_requested"
    PROMOTED = "promoted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CandidateRecord:
    candidate_id: str
    student_label: str
    dataset_id: str
    dataset_content_hash: str
    track: int
    state: CandidateState
    scorecard: Scorecard | None = None
    comparison: Comparison | None = None
    gate_result: GateResult | None = None


@dataclass(frozen=True)
class PromotionDecision:
    """The permission-ladder verdict for a promotion request. NEVER promotes."""

    candidate_id: str
    requires_approval: bool
    rung: str  # mirrors the contract PermissionRung: "execute-with-permission"
    eligible: bool
    reason: str


@dataclass(frozen=True)
class PromotionRecord:
    """Immutable record of an APPROVED promotion (who/when). Append-only."""

    candidate_id: str
    student_label: str
    approved_by: UUID
    approved_at: datetime
    previous_active: str | None
    dataset_content_hash: str
    track: int = TRACK_ID


class PromotionNotApproved(RuntimeError):
    """Raised if a promotion is attempted without an eligible request + approver."""


class ModelRegistry:
    """In-memory registry. The history list is append-only (immutable records)."""

    def __init__(self) -> None:
        self._candidates: dict[str, CandidateRecord] = {}
        self._history: list[PromotionRecord] = []
        self._active_track2: str | None = None  # candidate_id currently serving

    # -- lifecycle -----------------------------------------------------------

    def register(
        self,
        *,
        candidate_id: str,
        student_label: str,
        dataset_id: str,
        dataset_content_hash: str,
        track: int = TRACK_ID,
    ) -> CandidateRecord:
        if track != TRACK_ID:
            raise ValueError("only Track 2 candidates may enter the foundry registry")
        if candidate_id in self._candidates:
            raise ValueError(f"candidate {candidate_id} already registered")
        rec = CandidateRecord(
            candidate_id=candidate_id,
            student_label=student_label,
            dataset_id=dataset_id,
            dataset_content_hash=dataset_content_hash,
            track=track,
            state=CandidateState.REGISTERED,
        )
        self._candidates[candidate_id] = rec
        return rec

    def attach_eval(
        self,
        *,
        candidate_id: str,
        scorecard: Scorecard,
        comparison: Comparison,
        gate_result: GateResult | None = None,
    ) -> CandidateRecord:
        rec = self._require(candidate_id)
        updated = replace(
            rec,
            scorecard=scorecard,
            comparison=comparison,
            gate_result=gate_result,
            state=CandidateState.EVALUATED,
        )
        self._candidates[candidate_id] = updated
        return updated

    # -- the permission ladder ----------------------------------------------

    def request_promotion(self, *, candidate_id: str) -> PromotionDecision:
        """Request promotion to serve learners. ALWAYS requires approval; this
        method NEVER promotes (INVARIANT 8)."""
        rec = self._require(candidate_id)

        if rec.state == CandidateState.REGISTERED or rec.comparison is None:
            eligible = False
            reason = "candidate has no eval scorecard; cannot request promotion"
        elif rec.gate_result is not None and not rec.gate_result.passed:
            # Absolute pedagogy/correctness/safety floors are not met; a candidate
            # that fails the gate is BLOCKED even if it beats a weak incumbent.
            eligible = False
            reason = (
                "eval gate not cleared (absolute floors): "
                + "; ".join(rec.gate_result.failures)
            )
        elif not rec.comparison.candidate_better:
            eligible = False
            reason = f"eval says candidate is not better: {rec.comparison.summary}"
        else:
            eligible = True
            reason = "eval clears the bar; human approval required to serve learners"

        if eligible:
            self._candidates[candidate_id] = replace(
                rec, state=CandidateState.PROMOTION_REQUESTED
            )

        return PromotionDecision(
            candidate_id=candidate_id,
            requires_approval=True,  # ALWAYS — promotion is consequential
            rung="execute-with-permission",
            eligible=eligible,
            reason=reason,
        )

    def approve_promotion(
        self,
        *,
        candidate_id: str,
        approved_by: UUID,
        approved_at: datetime | None = None,
    ) -> PromotionRecord:
        """Advance an eligible, requested candidate into the Track 2 slot.

        Requires a genuine human approver (opaque ref). Raises if the candidate
        was not first put through :meth:`request_promotion` and found eligible.
        Writes an IMMUTABLE history record (who/when).
        """
        rec = self._require(candidate_id)
        if rec.state != CandidateState.PROMOTION_REQUESTED:
            raise PromotionNotApproved(
                f"candidate {candidate_id} is '{rec.state.value}', not a requested promotion"
            )
        if approved_by is None:  # type: ignore[comparison-overlap]
            raise PromotionNotApproved("an explicit human approver is required")
        if rec.track != TRACK_ID:
            raise ValueError("only Track 2 candidates may be promoted to the Track 2 slot")

        record = PromotionRecord(
            candidate_id=candidate_id,
            student_label=rec.student_label,
            approved_by=approved_by,
            approved_at=approved_at or datetime.now(timezone.utc),
            previous_active=self._active_track2,
            dataset_content_hash=rec.dataset_content_hash,
        )
        self._history.append(record)  # append-only, never rewritten
        self._active_track2 = candidate_id
        self._candidates[candidate_id] = replace(rec, state=CandidateState.PROMOTED)
        return record

    def reject_promotion(self, *, candidate_id: str, reason: str = "") -> CandidateRecord:
        rec = self._require(candidate_id)
        updated = replace(rec, state=CandidateState.REJECTED)
        self._candidates[candidate_id] = updated
        return updated

    # -- reads ---------------------------------------------------------------

    def active_track2(self) -> str | None:
        """The candidate_id currently serving in the Track 2 slot (or None)."""
        return self._active_track2

    def get(self, candidate_id: str) -> CandidateRecord:
        return self._require(candidate_id)

    def history(self) -> tuple[PromotionRecord, ...]:
        """Immutable promotion history (who/when), append-only order."""
        return tuple(self._history)

    def _require(self, candidate_id: str) -> CandidateRecord:
        rec = self._candidates.get(candidate_id)
        if rec is None:
            raise KeyError(f"unknown candidate {candidate_id}")
        return rec
