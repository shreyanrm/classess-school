"""Individual Education Plan (IEP) + intervention history (B8).

The doc (section 14): the profile "supports individual education plans and
intervention history where needed." An IEP is a learner-specific, goal-oriented
plan; the intervention history is the append-only record of what was tried, when,
and what followed — each entry evidence-linked.

Hard rules honoured here:

  - HUMAN IS ALWAYS FINAL + PERMISSION LADDER (invariant 5 of the LAWS). An IEP
    goal is RECOMMENDED/PREPARED, never auto-activated. Activating a plan and
    closing an intervention are CONSEQUENTIAL acts: the prepare path returns a
    ``requires_approval`` proposal; only an explicit human approval activates it.
    Nothing consequential fires automatically.
  - EVERY ENTRY LINKS TO EVIDENCE (principle 7). An intervention record and a
    goal's progress note both carry their source event-ids.
  - GATED. Reads pass the consent + purpose gate (scope ``mastery-profile``,
    purpose typically ``intervention``). Denied-by-default.
  - PLAIN LANGUAGE ONLY. Goal text and progress notes carry no number/percentage
    /formula — guarded via :func:`profile.assert_plain_language`.
  - PII-FREE + APPEND-ONLY. Opaque ids only; the history only ever APPENDS — a
    review or closure is a NEW entry, never an in-place mutation of evidence.

B8 does NOT decide an intervention worked (that is the spine's effectiveness
read). It MODELS the plan, HOLDS the append-only history, and GATES the reads.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable

from .access import ConsentGrant, ReadRequest, require
from .profile import assert_plain_language


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


class GoalStatus(str, Enum):
    """Lifecycle of an IEP goal. Only a human approval moves PROPOSED -> ACTIVE."""

    PROPOSED = "proposed"     # prepared, awaiting human approval (never auto-active)
    ACTIVE = "active"         # a human approved it
    MET = "met"               # evidence shows it was achieved (human-confirmed)
    WITHDRAWN = "withdrawn"   # closed without being met


class InterventionStatus(str, Enum):
    """Lifecycle of one intervention in the history."""

    PROPOSED = "proposed"     # recommended, awaiting human approval
    ACTIVE = "active"         # a human started it
    CLOSED = "closed"         # a human ended it (with an outcome note)


@dataclass(frozen=True)
class GoalProgressNote:
    """An append-only, evidence-linked progress note on an IEP goal.

    A progress note records what the latest evidence shows about a goal —
    "is retelling shorter passages now, still needs help with longer ones". It
    is plain language (no number), carries its source event-ids, and is never
    a judgement that the goal is met (only a human closes a goal). Notes are
    appended; they never mutate earlier notes.
    """

    note_id: str
    plain_language: str                # what the evidence shows, no number
    source_event_ids: tuple[str, ...]
    noted_at: datetime
    author_role: str = "system"        # learner / teacher / system

    def __post_init__(self) -> None:
        assert_plain_language(self.plain_language)
        if not self.source_event_ids:
            raise ValueError(
                "A goal progress note must link to its evidence events — no "
                "note without evidence (evidence over assertion)."
            )


@dataclass(frozen=True)
class IEPGoal:
    """One goal on an Individual Education Plan. Plain language; evidence-linked.

    A goal is created PROPOSED. It carries no number — "read a short passage and
    retell it in their own words", never a target percentage.

    Progress notes are APPEND-ONLY: :func:`add_goal_progress_note` returns a new
    goal whose ``progress_notes`` has the note appended; the original is left
    intact (append-only spirit, the audit trail never loses a state). Closing a
    goal to MET / WITHDRAWN is CONSEQUENTIAL and human-final.
    """

    goal_id: str
    subject: str                       # opaque canonical_uuid
    topic_id: str                      # opaque ontology id the goal targets
    plain_language: str                # the human goal, no number
    status: GoalStatus
    source_event_ids: tuple[str, ...]  # the evidence that motivated the goal
    created_at: datetime
    approved_by: str | None = None     # opaque ref of the human who approved
    approved_at: datetime | None = None
    progress_notes: tuple[GoalProgressNote, ...] = ()
    closed_by: str | None = None       # opaque ref of the human who closed it
    closed_at: datetime | None = None

    def __post_init__(self) -> None:
        assert_plain_language(self.plain_language)
        if not self.source_event_ids:
            raise ValueError(
                "An IEP goal must link to the evidence that motivated it — no "
                "goal without evidence (evidence over assertion)."
            )


@dataclass(frozen=True)
class InterventionRecord:
    """One entry in the append-only intervention history. Evidence-linked."""

    intervention_id: str
    subject: str
    goal_id: str | None                # the goal it serves, if any
    plain_language: str                # what was tried, plain language
    status: InterventionStatus
    started_at: datetime
    source_event_ids: tuple[str, ...]
    outcome_note: str = ""             # plain-language follow-up, set on close
    closed_at: datetime | None = None

    def __post_init__(self) -> None:
        assert_plain_language(self.plain_language)
        if self.outcome_note:
            assert_plain_language(self.outcome_note)
        if not self.source_event_ids:
            raise ValueError(
                "An intervention record must link to its evidence events."
            )


@dataclass(frozen=True)
class ApprovalRequired:
    """A prepared, consequential action awaiting a human decision.

    The PERMISSION LADDER: B8 prepares an IEP-goal activation or an intervention
    closure and returns this instead of firing it. A surface renders it as
    "approve / decline"; only :func:`approve_goal` / :func:`close_intervention`
    with an explicit human ref makes it real. Mirrors the requires_approval
    contract used across the platform.
    """

    action: str                        # e.g. "iep.goal.activate"
    target_id: str                     # opaque id of the goal/intervention
    rationale: str                     # plain-language WHY (explainable)
    source_event_ids: tuple[str, ...]
    requires_approval: bool = True

    def __post_init__(self) -> None:
        assert_plain_language(self.rationale)


def propose_goal(
    *,
    subject: str,
    topic_id: str,
    plain_language: str,
    source_event_ids: Iterable[str],
    created_at: datetime | None = None,
    goal_id: str | None = None,
) -> IEPGoal:
    """Prepare an IEP goal. Created PROPOSED — never auto-active (human final)."""
    return IEPGoal(
        goal_id=goal_id or _new_id(),
        subject=subject,
        topic_id=topic_id,
        plain_language=plain_language,
        status=GoalStatus.PROPOSED,
        source_event_ids=tuple(source_event_ids),
        created_at=created_at or _now(),
    )


def prepare_goal_activation(goal: IEPGoal, *, rationale: str) -> ApprovalRequired:
    """Prepare (do NOT fire) the activation of a proposed goal.

    Returns a ``requires_approval`` proposal. Activating a plan is consequential;
    the human approves it explicitly via :func:`approve_goal`.
    """
    if goal.status is not GoalStatus.PROPOSED:
        raise ValueError("Only a proposed goal can be prepared for activation.")
    return ApprovalRequired(
        action="iep.goal.activate",
        target_id=goal.goal_id,
        rationale=rationale,
        source_event_ids=goal.source_event_ids,
    )


def approve_goal(goal: IEPGoal, *, approved_by: str, approved_at: datetime | None = None) -> IEPGoal:
    """Activate a goal — the explicit HUMAN approval step (human is final).

    ``approved_by`` is the opaque ref of the deciding human; an empty ref is
    refused so no activation is ever unattributed.
    """
    if not approved_by:
        raise ValueError("Goal activation requires the approving human's opaque ref.")
    if goal.status is not GoalStatus.PROPOSED:
        raise ValueError("Only a proposed goal can be approved into active.")
    return replace(
        goal,
        status=GoalStatus.ACTIVE,
        approved_by=approved_by,
        approved_at=approved_at or _now(),
    )


def add_goal_progress_note(
    goal: IEPGoal,
    *,
    plain_language: str,
    source_event_ids: Iterable[str],
    author_role: str = "system",
    noted_at: datetime | None = None,
    note_id: str | None = None,
) -> IEPGoal:
    """Append an evidence-linked progress note to a goal (append-only).

    Recording progress is observational, not consequential — it does NOT move a
    goal to MET; only a human closure does that. The note is refused on a goal
    that is already closed (met/withdrawn) so the history of a finished goal is
    immutable. Returns a new goal with the note appended; the original is intact.
    """
    if goal.status in (GoalStatus.MET, GoalStatus.WITHDRAWN):
        raise ValueError("Cannot add a progress note to a closed goal (met/withdrawn).")
    note = GoalProgressNote(
        note_id=note_id or _new_id(),
        plain_language=plain_language,
        source_event_ids=tuple(source_event_ids),
        noted_at=noted_at or _now(),
        author_role=author_role,
    )
    return replace(goal, progress_notes=goal.progress_notes + (note,))


def prepare_goal_closure(
    goal: IEPGoal, *, outcome: GoalStatus, rationale: str
) -> ApprovalRequired:
    """Prepare (do NOT fire) closing a goal to MET or WITHDRAWN.

    Closing a goal is CONSEQUENTIAL (it ends a plan a learner is held to), so it
    returns a ``requires_approval`` proposal — a human decides via
    :func:`close_goal`. Only MET / WITHDRAWN are valid closure outcomes; an
    active goal is the only thing that can be closed.
    """
    if outcome not in (GoalStatus.MET, GoalStatus.WITHDRAWN):
        raise ValueError("A goal closure outcome must be MET or WITHDRAWN.")
    if goal.status is not GoalStatus.ACTIVE:
        raise ValueError("Only an active goal can be prepared for closure.")
    return ApprovalRequired(
        action=f"iep.goal.{outcome.value}",
        target_id=goal.goal_id,
        rationale=rationale,
        source_event_ids=goal.source_event_ids,
    )


def close_goal(
    goal: IEPGoal,
    *,
    outcome: GoalStatus,
    closed_by: str,
    closed_at: datetime | None = None,
) -> IEPGoal:
    """Close a goal to MET or WITHDRAWN — the explicit HUMAN step (human final).

    ``closed_by`` is the opaque ref of the deciding human; an empty ref is
    refused so no closure is ever unattributed. Only an active goal can close,
    and only to MET / WITHDRAWN.
    """
    if not closed_by:
        raise ValueError("Closing a goal requires the deciding human's opaque ref.")
    if outcome not in (GoalStatus.MET, GoalStatus.WITHDRAWN):
        raise ValueError("A goal can only close to MET or WITHDRAWN.")
    if goal.status is not GoalStatus.ACTIVE:
        raise ValueError("Only an active goal can be closed.")
    return replace(
        goal,
        status=outcome,
        closed_by=closed_by,
        closed_at=closed_at or _now(),
    )


class InterventionHistory:
    """The append-only intervention-history timeline for one learner.

    Append-only (invariant 5): a closure is a NEW state superseding the open
    record; nothing is mutated or deleted in place.
    """

    def __init__(self, subject: str) -> None:
        self._subject = subject
        self._records: list[InterventionRecord] = []

    @property
    def subject(self) -> str:
        return self._subject

    def record(
        self,
        *,
        plain_language: str,
        source_event_ids: Iterable[str],
        goal_id: str | None = None,
        status: InterventionStatus = InterventionStatus.PROPOSED,
        started_at: datetime | None = None,
        intervention_id: str | None = None,
    ) -> InterventionRecord:
        """Append an intervention to the history (PROPOSED by default)."""
        rec = InterventionRecord(
            intervention_id=intervention_id or _new_id(),
            subject=self._subject,
            goal_id=goal_id,
            plain_language=plain_language,
            status=status,
            started_at=started_at or _now(),
            source_event_ids=tuple(source_event_ids),
        )
        self._records.append(rec)
        return rec

    def prepare_closure(
        self, intervention_id: str, *, rationale: str
    ) -> ApprovalRequired:
        """Prepare (do NOT fire) closing an intervention — consequential, so it
        returns a ``requires_approval`` proposal for a human to decide."""
        rec = self._get(intervention_id)
        if rec.status is InterventionStatus.CLOSED:
            raise ValueError("Intervention is already closed.")
        return ApprovalRequired(
            action="iep.intervention.close",
            target_id=intervention_id,
            rationale=rationale,
            source_event_ids=rec.source_event_ids,
        )

    def close(
        self,
        intervention_id: str,
        *,
        outcome_note: str,
        closed_by: str,
        closed_at: datetime | None = None,
    ) -> InterventionRecord:
        """Close an intervention — explicit HUMAN step (human is final).

        Append-only: the open record is superseded by a new CLOSED record in the
        history; the original is left in place as part of the audit trail.
        """
        if not closed_by:
            raise ValueError("Closing an intervention requires the deciding human's opaque ref.")
        rec = self._get(intervention_id)
        if rec.status is InterventionStatus.CLOSED:
            raise ValueError("Intervention is already closed.")
        closed = replace(
            rec,
            status=InterventionStatus.CLOSED,
            outcome_note=outcome_note,
            closed_at=closed_at or _now(),
        )
        self._records.append(closed)
        return closed

    def _get(self, intervention_id: str) -> InterventionRecord:
        # The latest state for this id (append-only supersedes earlier states).
        for rec in reversed(self._records):
            if rec.intervention_id == intervention_id:
                return rec
        raise KeyError("No such intervention in this history.")

    def all(self) -> tuple[InterventionRecord, ...]:
        """Owner's full append-only view (every state ever recorded)."""
        return tuple(self._records)

    def current(self) -> tuple[InterventionRecord, ...]:
        """The latest state per intervention id, oldest-started first — the
        intervention-history TIMELINE a surface renders."""
        latest: dict[str, InterventionRecord] = {}
        for rec in self._records:
            latest[rec.intervention_id] = rec
        return tuple(sorted(latest.values(), key=lambda r: r.started_at))

    def gated_view(
        self,
        *,
        request: ReadRequest,
        grants: Iterable[ConsentGrant],
        asof: datetime | None = None,
    ) -> tuple[InterventionRecord, ...]:
        """A consent + purpose-gated read of the intervention history.

        GATED FIRST (denied-by-default). Scope must be ``mastery-profile``.
        Returns the current per-intervention timeline on ALLOW; raises
        ``ConsentDenied`` otherwise.
        """
        require(request, grants, asof=asof)
        return self.current()


__all__ = [
    "GoalStatus",
    "InterventionStatus",
    "GoalProgressNote",
    "IEPGoal",
    "InterventionRecord",
    "ApprovalRequired",
    "propose_goal",
    "prepare_goal_activation",
    "approve_goal",
    "add_goal_progress_note",
    "prepare_goal_closure",
    "close_goal",
    "InterventionHistory",
]
