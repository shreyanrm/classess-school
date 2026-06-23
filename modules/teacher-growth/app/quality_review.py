"""Quality review workflow (B10).

A quality review is the HUMAN-OWNED process where a reviewer (a peer, a mentor, a
coordinator) and the teacher discuss practice. B10's job is to model that process
so it is fair, evidence-linked, and never decided by a machine.

Invariants made concrete here:

  - **Human authority on anything consequential (INVARIANT 8 / principle 3).**
    A review moves through ``draft -> teacher_reflection -> reviewer_review ->
    awaiting_sign_off -> closed``. It is closed (finalised) only by an explicit
    human ``reviewer_ref`` calling :meth:`QualityReview.sign_off`. There is no
    auto-close, no auto-rating, and no path where the AI finalises a review.

  - **Teacher-first.** The teacher adds their own reflection BEFORE the reviewer
    finalises, and a coaching signal can only enter a review with the teacher's
    consent — coaching evidence stays private unless the teacher brings it in.

  - **Evidence over assertion (principle 7).** Every finding carries linked
    evidence (a lesson id + an interaction-derived note); a finding cannot be a
    bare verdict. Reviews capture growth notes, not a punitive grade.

  - **Opaque refs only (INVARIANT 1 + 2).** ``teacher_ref`` and ``reviewer_ref``
    are opaque canonical_uuids; no names/PII enter the record.

Pure state machine; deterministic; no network/DB. Persistence and routing to a
human reviewer happen through the gateway + A5 workflow engine when wired (see
``config.py``); absent those, the workflow runs fully in memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from .coaching import CoachingSignal, employment_decision_guard


ReviewState = Literal[
    "draft",
    "teacher_reflection",
    "reviewer_review",
    "awaiting_sign_off",
    "closed",
]

FindingKind = Literal["strength", "growth_area"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ReviewFinding:
    """One evidence-linked observation in a review. Never a bare verdict."""

    kind: FindingKind
    note: str
    lesson_id: str
    evidence: str

    def __post_init__(self) -> None:
        if not self.note.strip():
            raise ValueError("A finding must carry a note (no empty findings).")
        if not self.evidence.strip():
            raise ValueError(
                "A finding must link evidence — evidence over assertion."
            )


class ReviewStateError(RuntimeError):
    """Raised on an illegal state transition in the review workflow."""


@dataclass
class QualityReview:
    """A single human-owned quality review for one teacher.

    The AI may PREPARE the review (assemble evidence, draft findings) but a human
    OWNS every consequential transition. The teacher reflects first; the reviewer
    signs off last; nothing auto-finalises.
    """

    review_id: str
    teacher_ref: str
    cycle: str  # opaque review cycle/term label, e.g. "2026-T1".
    state: ReviewState = "draft"

    findings: list[ReviewFinding] = field(default_factory=list)
    teacher_reflection: str | None = None
    reviewer_ref: str | None = None
    reviewer_summary: str | None = None
    # Coaching signals the TEACHER chose to bring in (private otherwise).
    shared_coaching_signals: list[CoachingSignal] = field(default_factory=list)

    created_at: str = field(default_factory=_now_iso)
    history: list[str] = field(default_factory=list)

    # -- preparation (AI- or human-prepared; not consequential) ------------

    def add_finding(self, finding: ReviewFinding) -> None:
        """Attach an evidence-linked finding while the review is still open."""
        if self.state in ("awaiting_sign_off", "closed"):
            raise ReviewStateError(
                "Cannot add findings once the review is awaiting sign-off or closed."
            )
        self.findings.append(finding)
        self.history.append(f"finding_added:{finding.kind}@{_now_iso()}")

    def attach_coaching_signal(
        self, signal: CoachingSignal, *, teacher_consent_ref: str
    ) -> None:
        """Bring a private coaching signal into the review — TEACHER-CONSENTED only.

        Coaching signals are private and teacher-first (see ``coaching.py``). They
        enter a review only when the teacher supplies their own consent ref,
        honouring the CONSENT gate on a cross-context read (INVARIANT 6).
        """
        if not teacher_consent_ref:
            raise PermissionError(
                "A coaching signal is private; it can enter a review only with the "
                "teacher's explicit consent ref."
            )
        self.shared_coaching_signals.append(signal)
        self.history.append(f"coaching_signal_shared:{signal.dimension}@{_now_iso()}")

    # -- the human-owned workflow ------------------------------------------

    def open_for_teacher_reflection(self) -> None:
        """Move a drafted review to the teacher so they reflect FIRST."""
        if self.state != "draft":
            raise ReviewStateError("Only a draft review can be opened for reflection.")
        self.state = "teacher_reflection"
        self.history.append(f"opened_for_teacher_reflection@{_now_iso()}")

    def submit_teacher_reflection(self, reflection: str) -> None:
        """The teacher records their own reflection before the reviewer reviews."""
        if self.state != "teacher_reflection":
            raise ReviewStateError(
                "Teacher reflection is accepted only in the teacher_reflection state."
            )
        if not reflection.strip():
            raise ValueError("Reflection cannot be empty.")
        self.teacher_reflection = reflection
        self.state = "reviewer_review"
        self.history.append(f"teacher_reflection_submitted@{_now_iso()}")

    def record_reviewer_review(
        self, *, reviewer_ref: str, reviewer_summary: str
    ) -> None:
        """A human reviewer records their summary, moving toward sign-off."""
        if self.state != "reviewer_review":
            raise ReviewStateError(
                "A reviewer summary is accepted only after teacher reflection."
            )
        if not reviewer_ref:
            raise PermissionError("A reviewer review requires a human reviewer_ref.")
        if not reviewer_summary.strip():
            raise ValueError("Reviewer summary cannot be empty.")
        self.reviewer_ref = reviewer_ref
        self.reviewer_summary = reviewer_summary
        self.state = "awaiting_sign_off"
        self.history.append(f"reviewer_review_recorded@{_now_iso()}")

    def sign_off(self, *, reviewer_ref: str) -> None:
        """Finalise the review — the single consequential, human-only action.

        Refuses to close without a human reviewer_ref, refuses to let anyone but
        the reviewer who reviewed it sign off, and never auto-fires. This is the
        permission ladder's ``execute_with_permission`` rung for a review.
        """
        if self.state != "awaiting_sign_off":
            raise ReviewStateError(
                "A review can be signed off only when awaiting sign-off."
            )
        if not reviewer_ref:
            raise PermissionError(
                "Sign-off requires a human reviewer_ref. A review never auto-closes."
            )
        if reviewer_ref != self.reviewer_ref:
            raise PermissionError(
                "Only the reviewer who recorded the review may sign it off."
            )
        self.state = "closed"
        self.history.append(f"signed_off_by_human@{_now_iso()}")

    # -- explicit refusals --------------------------------------------------

    def auto_finalise(self) -> None:
        """There is NO automatic finalisation. This always refuses.

        Finalising a quality review is consequential and may feed a human
        employment decision; the AI never closes it (INVARIANT 8).
        """
        employment_decision_guard()

    # -- read helpers -------------------------------------------------------

    @property
    def is_closed(self) -> bool:
        return self.state == "closed"

    @property
    def strengths(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.kind == "strength"]

    @property
    def growth_areas(self) -> list[ReviewFinding]:
        return [f for f in self.findings if f.kind == "growth_area"]

    def why_am_i_seeing_this(self) -> str:
        return (
            "This quality review is a human-owned conversation about your "
            "practice. You reflect first; a human reviewer signs off. No part of "
            "it is decided automatically."
        )


def start_review(*, review_id: str, teacher_ref: str, cycle: str) -> QualityReview:
    """Open a new quality review in the ``draft`` state. Opaque refs only."""
    if not teacher_ref:
        raise ValueError("A review requires a teacher_ref (opaque).")
    return QualityReview(review_id=review_id, teacher_ref=teacher_ref, cycle=cycle)
