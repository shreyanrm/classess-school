"""Parent–teacher meetings (B9) — book, prepare, follow up.

The dossier / B9: PTM scheduling/prep/follow-up. The parent surfaces:

  - ``/parent/ptm``         — Book, prepare, follow up. Booking is PERMISSION-
                              GATED; reminders.
  - ``/parent/ptm-prep``    — Walk in informed. The child's brief + space to
                              submit questions ahead; questions REACH the
                              teacher's PTM prep.
  - ``/parent/ptm-followup``— The agreed plan and your part. A table
                              (action · owner · due) with the parent's items
                              highlighted.

This is the PTM LIFECYCLE around the in-meeting silent assistant
(:mod:`meeting_assistant`, which owns transcription/notes/action-extraction WITH
consent). This module owns the booking and the parent-facing wrapping, and reuses
the assistant's prepared (never auto-fired) action items for the follow-up plan.

Three non-negotiables, enforced in code:

  1. **Booking is permission-gated (permission ladder, INVARIANT 8).** A request
     is PREPARED (proposed) and a real booking only exists once a human (the
     teacher / the slot owner) CONFIRMS it. The system never auto-books. This
     mirrors ApprovalControl on the surfaces: prepare → confirm.
  2. **Pre-submitted questions are screened (child-safety on every free-text
     surface).** A parent's question is free text bound for a teacher; it passes
     the same :class:`Safeguard` the hub uses before it is admitted to the prep.
     A flagged question does not silently route to a teacher — it is a
     safeguarding matter handed to a qualified human.
  3. **The follow-up plan is partnership-shaped + owned.** Each agreed action has
     an owner role, a due window, and a follow-up; the PARENT's items are
     highlighted (their part), and an action is only "assigned" once a human owns
     it — never auto-assigned.

PII discipline: opaque refs + roles only; the child BRIEF is plain-language and
PII-free (it does not carry a raw score). Reminders carry a meeting ref + a plain
window, never personal contact details.

Import-safe + degrade-safe: pure synthesis over supplied inputs; no I/O, no
provider, no secret value read at import. Reminders are PREPARED here (records of
intent) and delivered through the multi-channel :mod:`delivery` layer — which
itself degrades to an in-memory outbox until a provider is wired.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from .config import CommunicationSettings, get_settings
from .meeting_assistant import ActionItem, MeetingNotes
from .safeguarding import Escalation, SafetyFinding, Safeguard


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


PTM_PURPOSE_LABEL = "parent_teacher_partnership"


class BookingStatus(str, Enum):
    """A PTM booking lifecycle. ``proposed`` until a human confirms (permission
    ladder); never auto-confirmed by the system."""

    PROPOSED = "proposed"      # prepared, awaiting the slot owner's confirmation.
    CONFIRMED = "confirmed"    # a human (teacher / slot owner) confirmed it.
    DECLINED = "declined"      # the slot owner declined the request.
    CANCELLED = "cancelled"    # a confirmed booking later cancelled by a human.


class BookingApprovalError(PermissionError):
    """Raised when a booking is acted on without the required human approval.
    Booking / cancelling a meeting is consequential — it never auto-fires."""


class PtmQuestionFlaggedError(RuntimeError):
    """Raised when a pre-submitted question is child-safety flagged. A flagged
    question is a safeguarding matter for a qualified human; it does not silently
    route into a teacher's prep."""


@dataclass(frozen=True)
class MeetingSlot:
    """An offered meeting slot. Plain window label + opaque owner ref."""

    slot_id: str
    owner_ref: str             # the teacher / slot owner (opaque).
    owner_role: str            # e.g. "teacher".
    starts_at: str             # ISO start; the canonical scheduled_for.
    window_label: str          # plain language, e.g. "Fri 3:30–3:45pm".


@dataclass
class PtmBooking:
    """A parent–teacher meeting booking. PROPOSED until a human confirms.

    Opaque participant refs only; partnership-shaped purpose. The booking is the
    trackable unit; its lifecycle is explicit and human-advanced.
    """

    booking_id: str
    slot: MeetingSlot
    parent_ref: str            # opaque canonical_uuid of the requesting parent.
    child_context_ref: str     # the opaque context the meeting is about.
    requested_at: str
    status: BookingStatus = BookingStatus.PROPOSED
    purpose_label: str = PTM_PURPOSE_LABEL
    confirmed_by_ref: str | None = None
    decided_at: str | None = None

    @property
    def is_confirmed(self) -> bool:
        return self.status is BookingStatus.CONFIRMED

    @property
    def scheduled_for(self) -> str:
        return self.slot.starts_at

    @property
    def participant_refs(self) -> list[str]:
        return [self.parent_ref, self.slot.owner_ref]

    def confirm(self, *, by_ref: str | None) -> "PtmBooking":
        """Confirm the booking — the slot owner's human act (permission ladder).

        Refuses without a ``by_ref``: booking is consequential and is confirmed
        by a person, never by the system."""
        if not by_ref:
            raise BookingApprovalError(
                "Confirming a PTM booking is consequential and requires the slot "
                "owner (by_ref). The system prepares a booking; a person confirms "
                "it — it never auto-books."
            )
        if self.status is BookingStatus.DECLINED:
            raise BookingApprovalError(
                "Cannot confirm a booking that was declined; request a new slot."
            )
        self.status = BookingStatus.CONFIRMED
        self.confirmed_by_ref = by_ref
        self.decided_at = _now_iso()
        return self

    def decline(self, *, by_ref: str | None) -> "PtmBooking":
        if not by_ref:
            raise BookingApprovalError(
                "Declining a PTM booking requires the slot owner (by_ref)."
            )
        self.status = BookingStatus.DECLINED
        self.decided_at = _now_iso()
        return self

    def cancel(self, *, by_ref: str | None) -> "PtmBooking":
        """Cancel a confirmed booking — a human act (never auto-cancelled)."""
        if not by_ref:
            raise BookingApprovalError(
                "Cancelling a PTM booking is consequential and requires a human "
                "actor (by_ref)."
            )
        self.status = BookingStatus.CANCELLED
        self.decided_at = _now_iso()
        return self


@dataclass(frozen=True)
class PtmReminder:
    """A PREPARED reminder of an upcoming PTM. A record of intent — it is handed
    to the delivery layer to actually send (which is itself permission-gated /
    degrade-safe). Carries a meeting ref + plain window, never contact details."""

    booking_id: str
    recipient_ref: str
    when_label: str            # plain language, e.g. "tomorrow at 3:30pm".
    body: str                  # plain-language reminder text (no PII).


@dataclass(frozen=True)
class PtmQuestion:
    """A parent's pre-submitted question, SCREENED before it reaches the teacher.

    The body stays in the monitored store; the finding rides so the teacher's
    prep knows a qualified human is involved if it was flagged (it never is in
    the happy path — a flagged question is escalated, not routed)."""

    question_id: str
    booking_id: str
    parent_ref: str
    body: str
    finding: SafetyFinding
    submitted_at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class PtmPrep:
    """What a parent walks in with: a plain-language child brief + their
    screened pre-submitted questions that reached the teacher."""

    booking_id: str
    child_brief: str           # plain language, PII-free, no raw score.
    questions: tuple[PtmQuestion, ...]

    @property
    def question_count(self) -> int:
        return len(self.questions)


@dataclass(frozen=True)
class FollowUpAction:
    """One row of the shared follow-up plan: action · owner · due.

    Reuses the silent assistant's :class:`ActionItem` shape (proposed, owner role,
    timeline, follow-up) and adds whether it is the PARENT's part (highlighted on
    the parent surface) and whether a human has yet OWNED it (assigned)."""

    description: str
    owner_role: str
    due: str
    follow_up: str
    is_parent_item: bool
    owner_ref: str | None = None       # set only once a human owns it.
    assigned_by_ref: str | None = None  # the human who assigned the owner.

    @property
    def is_assigned(self) -> bool:
        return bool(self.owner_ref and self.assigned_by_ref)

    def assign_to(self, *, owner_ref: str, by_ref: str | None) -> "FollowUpAction":
        """Give the action a human OWNER. The system never auto-assigns; a person
        assigns ownership (permission ladder)."""
        if not by_ref:
            raise BookingApprovalError(
                "Assigning an owner to a follow-up action is a human act on the "
                "permission ladder (by_ref); it never auto-assigns."
            )
        if not owner_ref:
            raise ValueError("An assigned action must have a human owner (owner_ref).")
        return FollowUpAction(
            description=self.description,
            owner_role=self.owner_role,
            due=self.due,
            follow_up=self.follow_up,
            is_parent_item=self.is_parent_item,
            owner_ref=owner_ref,
            assigned_by_ref=by_ref,
        )


@dataclass(frozen=True)
class PtmFollowUp:
    """The agreed plan after a PTM. The parent's items are highlighted."""

    booking_id: str
    actions: tuple[FollowUpAction, ...]
    summary: str               # a calm, plain-language one-liner.

    @property
    def parent_items(self) -> tuple[FollowUpAction, ...]:
        return tuple(a for a in self.actions if a.is_parent_item)


class PtmService:
    """Book, prepare, and follow up on parent–teacher meetings.

    Booking is permission-gated (proposed → human-confirmed); pre-submitted
    questions are child-safety screened before they reach a teacher; the
    follow-up plan is partnership-shaped with the parent's part highlighted.
    Deterministic + offline; degrades cleanly with nothing wired.
    """

    def __init__(
        self,
        *,
        guard: Safeguard | None = None,
        settings: CommunicationSettings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        # Free-text questions are screened on the same wall the hub uses.
        self._guard = guard or Safeguard(self._settings)
        self._bookings: dict[str, PtmBooking] = {}

    @property
    def settings(self) -> CommunicationSettings:
        return self._settings

    @property
    def guard(self) -> Safeguard:
        return self._guard

    def bookings(self) -> list[PtmBooking]:
        return list(self._bookings.values())

    # -- 1. Book (permission-gated) ----------------------------------------

    def request_booking(
        self,
        *,
        slot: MeetingSlot,
        parent_ref: str,
        child_context_ref: str,
    ) -> PtmBooking:
        """Prepare a PTM booking request — PROPOSED, awaiting confirmation.

        This is the RECOMMEND step: the booking exists as a proposal until the
        slot owner confirms it. Nothing is scheduled yet (permission ladder).
        """
        if not parent_ref:
            raise ValueError("A PTM booking needs a requesting parent (parent_ref).")
        booking = PtmBooking(
            booking_id=str(uuid.uuid4()),
            slot=slot,
            parent_ref=parent_ref,
            child_context_ref=child_context_ref,
            requested_at=_now_iso(),
        )
        self._bookings[booking.booking_id] = booking
        return booking

    def confirm_booking(self, booking_id: str, *, by_ref: str | None) -> PtmBooking:
        """Confirm a proposed booking — the slot owner's human act. Only after
        this is the meeting real (and a ``ptm.scheduled`` event can be emitted by
        the caller). Refuses without ``by_ref``."""
        booking = self._bookings[booking_id]
        return booking.confirm(by_ref=by_ref)

    def reminders_for(
        self, booking: PtmBooking, *, when_label: str
    ) -> tuple[PtmReminder, ...]:
        """Prepare reminders for a CONFIRMED booking (one per participant).

        Refuses to remind about an unconfirmed booking — there is nothing to
        remind about until a human has confirmed the slot. The reminders are
        records of intent; the delivery layer actually sends them."""
        if not booking.is_confirmed:
            raise BookingApprovalError(
                "Cannot prepare reminders for a booking that is not confirmed. "
                "Confirm the slot first; the system never reminds about a meeting "
                "that does not yet exist."
            )
        body = (
            f"A parent–teacher meeting is coming up {when_label}. It is a short, "
            "shared conversation about how to support your child together."
        )
        return tuple(
            PtmReminder(
                booking_id=booking.booking_id,
                recipient_ref=ref,
                when_label=when_label,
                body=body,
            )
            for ref in booking.participant_refs
        )

    # -- 2. Prepare (screened questions reach the teacher) -----------------

    def prepare(
        self,
        *,
        booking: PtmBooking,
        child_brief: str,
        question_bodies: list[str] | None = None,
    ) -> PtmPrep:
        """Build the parent's prep: a plain-language child brief + their
        pre-submitted questions, each SCREENED before it reaches the teacher.

        A flagged question is NOT routed into the teacher's prep — it raises so
        the caller routes it to a qualified human (safeguarding), never silently
        delivering it. Clean questions are admitted and reach the teacher.
        """
        questions: list[PtmQuestion] = []
        for body in question_bodies or []:
            finding = self._guard.classify(body)
            if finding.flagged:
                raise PtmQuestionFlaggedError(
                    "A pre-submitted question was child-safety flagged. It is not "
                    "routed to the teacher's prep; it is a safeguarding matter for "
                    "a qualified human. Nothing is silently delivered."
                )
            questions.append(
                PtmQuestion(
                    question_id=str(uuid.uuid4()),
                    booking_id=booking.booking_id,
                    parent_ref=booking.parent_ref,
                    body=body,
                    finding=finding,
                )
            )
        return PtmPrep(
            booking_id=booking.booking_id,
            child_brief=child_brief,
            questions=tuple(questions),
        )

    # -- 3. Follow up (shared plan; parent's part highlighted) -------------

    def follow_up(
        self,
        *,
        booking: PtmBooking,
        notes: MeetingNotes,
        parent_owner_roles: tuple[str, ...] = ("parent",),
    ) -> PtmFollowUp:
        """Build the shared follow-up plan from the meeting's notes.

        Reuses the silent assistant's PROPOSED action items (owner role, timeline,
        follow-up) — never auto-fired — and highlights the PARENT's items so the
        parent surface can show 'your part'. Actions stay unassigned until a human
        owns them.
        """
        actions = tuple(
            self._to_follow_up(item, parent_owner_roles=parent_owner_roles)
            for item in notes.action_items
        )
        parent_count = sum(1 for a in actions if a.is_parent_item)
        summary = (
            f"You agreed {len(actions)} thing(s) together; "
            f"{parent_count} is your part. Small, shared, and doable."
            if actions
            else "No actions were agreed — a calm check-in is enough for now."
        )
        return PtmFollowUp(
            booking_id=booking.booking_id,
            actions=actions,
            summary=summary,
        )

    @staticmethod
    def _to_follow_up(
        item: ActionItem, *, parent_owner_roles: tuple[str, ...]
    ) -> FollowUpAction:
        return FollowUpAction(
            description=item.description,
            owner_role=item.owner_role,
            due=item.timeline,
            follow_up=item.follow_up,
            is_parent_item=item.owner_role in parent_owner_roles,
        )
