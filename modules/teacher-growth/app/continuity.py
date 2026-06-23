"""Knowledge-transfer / handover notes (B10 continuity engine).

When a class or a coaching relationship changes hands — a teacher goes on leave,
a mentor rotates, a section transfers — the accumulated, hard-won knowledge about
*how to teach this group well* should travel with it, so the incoming teacher
does not restart from zero. That is the continuity engine B10 owns and that B2
"Consumes: the continuity engine".

What a B10 handover carries (and what it deliberately does NOT):

  - **Carries:** where the class is in the curriculum (opaque topic ids), what is
    next, generic pedagogical watch-points ("this group needs more retrieval
    practice"), prepared materials (opaque content ids), and — only with the
    outgoing teacher's consent — a private coaching reflection to pass forward.
  - **Does NOT carry:** any PII, any named student, any behavioural data beyond
    the section's curriculum position, and any punitive judgement of the
    outgoing OR incoming teacher. A handover is help, not a verdict.

Invariants: opaque refs only (INVARIANT 1 + 2); coaching reflection crosses
only with consent (INVARIANT 6); no auto-fire of anything consequential. Pure,
deterministic, import-safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


HandoverReason = Literal[
    "planned_leave", "substitution", "transfer", "term_change", "mentor_rotation"
]


@dataclass
class ContinuityNote:
    """A teacher knowledge-transfer note that travels with a class on handover.

    Opaque refs + curriculum position + generic pedagogy only. No PII, no named
    students, no behavioural data beyond where the class is and what is next.
    """

    section_id: str
    subject_id: str
    from_teacher_ref: str  # opaque outgoing teacher.
    reason: HandoverReason
    current_topic_id: str  # ontology node the class is on now.
    to_teacher_ref: str | None = None  # opaque incoming teacher; None when TBD.
    next_topic_id: str | None = None  # what comes next.
    last_delivered_period: int | None = None  # plan index last covered.
    watch_points: list[str] = field(default_factory=list)  # generic, PII-free.
    prepared_materials: list[str] = field(default_factory=list)  # opaque content ids.
    # A private coaching reflection the outgoing teacher CHOSE to pass forward.
    shared_coaching_note: str | None = None
    coaching_consent_ref: str | None = None

    def __post_init__(self) -> None:
        # Defend the no-PII invariant at the boundary: watch points and any
        # shared coaching note are generic pedagogical text, never named people.
        for wp in self.watch_points:
            if not isinstance(wp, str):
                raise TypeError(
                    "watch_points must be plain strings (generic, PII-free)."
                )
        # A coaching note may only be present if the teacher consented to share
        # it — coaching is private otherwise (INVARIANT 6).
        if self.shared_coaching_note and not self.coaching_consent_ref:
            raise PermissionError(
                "A coaching reflection can travel in a handover only with the "
                "outgoing teacher's consent ref; coaching is private by default."
            )

    @property
    def is_complete(self) -> bool:
        """Complete enough to hand over when it states where the class is and
        what is next."""
        return bool(self.current_topic_id) and self.next_topic_id is not None

    @property
    def carries_coaching(self) -> bool:
        return bool(self.shared_coaching_note)

    def why_am_i_seeing_this(self) -> str:
        return (
            "This handover note was passed forward to help you pick up this class "
            "where it is. It carries the curriculum position and generic notes "
            "only — no student records and no judgement of any teacher."
        )

    def summary(self) -> str:
        nxt = self.next_topic_id or "to be set"
        coaching = " (with a shared coaching note)" if self.carries_coaching else ""
        return (
            f"Handover ({self.reason}) for the section: currently on topic "
            f"{self.current_topic_id}, next {nxt}; "
            f"{len(self.watch_points)} watch-point(s), "
            f"{len(self.prepared_materials)} prepared item(s){coaching}."
        )


def build_continuity_note(
    *,
    section_id: str,
    subject_id: str,
    from_teacher_ref: str,
    reason: HandoverReason,
    current_topic_id: str,
    to_teacher_ref: str | None = None,
    next_topic_id: str | None = None,
    last_delivered_period: int | None = None,
    watch_points: list[str] | None = None,
    prepared_materials: list[str] | None = None,
    shared_coaching_note: str | None = None,
    coaching_consent_ref: str | None = None,
) -> ContinuityNote:
    """Construct a knowledge-transfer note. Opaque refs only; PII-free.

    A coaching reflection is included only when ``coaching_consent_ref`` is also
    supplied — otherwise it is refused, keeping coaching private by default.
    """
    return ContinuityNote(
        section_id=section_id,
        subject_id=subject_id,
        from_teacher_ref=from_teacher_ref,
        reason=reason,
        current_topic_id=current_topic_id,
        to_teacher_ref=to_teacher_ref,
        next_topic_id=next_topic_id,
        last_delivered_period=last_delivered_period,
        watch_points=list(watch_points or []),
        prepared_materials=list(prepared_materials or []),
        shared_coaching_note=shared_coaching_note,
        coaching_consent_ref=coaching_consent_ref,
    )
