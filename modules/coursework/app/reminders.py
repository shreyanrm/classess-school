"""Risk-based assignment reminders (B6, domain 9).

The dossier: "reminders are sent based on risk rather than generic spam". This
module computes WHO should be reminded about an assignment and HOW URGENTLY, from
risk signals — not a blanket message to everyone. A learner who has already
submitted is never reminded; a learner at high risk close to the deadline is
prioritised.

The hard rules:

  - PERMISSION LADDER: sending a message is a consequential action. This module
    PREPARES reminders and returns them at the PREPARE rung
    (``requires_approval`` true) — it NEVER auto-sends. A human (or an explicitly
    permitted, policy-bound automation outside this module) dispatches them.
  - RISK-BASED, NOT SPAM: a reminder is only prepared for a learner who has NOT
    submitted, and its urgency is a function of time-to-due AND the learner's risk
    signal. Low-risk, plenty-of-time learners are not nagged.
  - NO PII: a learner is an opaque ``canonical_uuid``; the reminder carries only
    refs and a neutral message — never PII.

Pure: no I/O, no network, no send. Import-safe. Delivery is a separate,
human-approved step that lives outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID


class ReminderUrgency(str, Enum):
    """How urgently a reminder should go out. Drives ordering, not auto-send."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class LearnerReminderState:
    """One learner's state for reminder decisions. ``risk`` in [0,1] is CONSUMED
    from the intelligence layer (not computed here): higher means likelier to miss
    the deadline (e.g. low recent engagement, history of late work). All refs are
    opaque; no PII."""

    canonical_uuid: UUID
    submitted: bool = False
    risk: float = 0.0


@dataclass(frozen=True)
class PreparedReminder:
    """A prepared (NOT sent) reminder for one learner. PREPARE rung: it requires
    human approval before dispatch. Carries a neutral message and the why, so the
    approver sees the reasoning."""

    canonical_uuid: UUID
    assignment_id: UUID
    urgency: ReminderUrgency
    hours_to_due: float
    risk: float
    message: str
    rationale: str
    reminder_id: UUID | None = None

    @property
    def rung(self) -> str:
        return "prepare"

    @property
    def requires_approval(self) -> bool:
        """Sending is consequential — always requires explicit human approval."""
        return True


@dataclass(frozen=True)
class ReminderPlan:
    """The prepared reminder set for one assignment — risk-ordered, with a summary.
    A RECOMMENDATION a human reviews and dispatches; nothing is auto-sent."""

    assignment_id: UUID
    reminders: list[PreparedReminder] = field(default_factory=list)
    skipped_submitted: int = 0
    skipped_low_risk: int = 0
    rationale: str = ""

    @property
    def rung(self) -> str:
        return "prepare"

    @property
    def requires_approval(self) -> bool:
        return True


# A learner below this risk with comfortable time left is NOT reminded (anti-spam).
_LOW_RISK_QUIET = 0.3
# Hours-to-due bands for urgency.
_DUE_SOON_HOURS = 24.0
_DUE_IMMINENT_HOURS = 6.0


def _urgency(hours_to_due: float, risk: float) -> ReminderUrgency:
    """Urgency from time-to-due and risk together. Imminent OR high-risk-soon is
    HIGH; otherwise risk and time blend to medium/low."""
    if hours_to_due <= _DUE_IMMINENT_HOURS or (risk >= 0.7 and hours_to_due <= _DUE_SOON_HOURS):
        return ReminderUrgency.HIGH
    if hours_to_due <= _DUE_SOON_HOURS or risk >= 0.6:
        return ReminderUrgency.MEDIUM
    return ReminderUrgency.LOW


def plan_reminders(
    *,
    assignment_id: UUID,
    due_at: datetime,
    learners: list[LearnerReminderState],
    now: datetime,
    quiet_below_risk: float = _LOW_RISK_QUIET,
) -> ReminderPlan:
    """Prepare risk-based reminders for an assignment.

    For each learner who has NOT submitted, an urgency is computed from the hours
    to the deadline and their risk signal. A low-risk learner with comfortable
    time left is skipped (anti-spam). Submitted learners are always skipped. The
    result is risk-then-urgency ordered and is PREPARED only — dispatch is a
    separate, human-approved action (``requires_approval`` is true).

    A past-due deadline still prepares reminders (negative hours -> HIGH urgency),
    so a chase-up can be approved; it never auto-sends.
    """
    reminders: list[PreparedReminder] = []
    skipped_submitted = 0
    skipped_low_risk = 0

    for lr in learners:
        if lr.submitted:
            skipped_submitted += 1
            continue
        hours_to_due = (due_at - now).total_seconds() / 3600.0
        comfortable_time = hours_to_due > _DUE_SOON_HOURS
        if lr.risk < quiet_below_risk and comfortable_time:
            # Low risk, plenty of time — do not nag.
            skipped_low_risk += 1
            continue
        urgency = _urgency(hours_to_due, lr.risk)
        if hours_to_due < 0:
            urgency = ReminderUrgency.HIGH
            when = f"was due {abs(hours_to_due):.0f}h ago"
        else:
            when = f"is due in {hours_to_due:.0f}h"
        message = f"A reminder: your assignment {when}. Let your teacher know if you need help."
        rationale = (
            f"Prepared because this learner has not submitted, risk {lr.risk:.2f}, "
            f"and the assignment {when}. Urgency {urgency.value}. Requires human approval to send."
        )
        reminders.append(
            PreparedReminder(
                canonical_uuid=lr.canonical_uuid,
                assignment_id=assignment_id,
                urgency=urgency,
                hours_to_due=hours_to_due,
                risk=lr.risk,
                message=message,
                rationale=rationale,
            )
        )

    _order = {ReminderUrgency.HIGH: 0, ReminderUrgency.MEDIUM: 1, ReminderUrgency.LOW: 2}
    reminders.sort(key=lambda r: (_order[r.urgency], -r.risk, r.hours_to_due))

    rationale = (
        f"Prepared {len(reminders)} risk-based reminder(s); skipped {skipped_submitted} who already "
        f"submitted and {skipped_low_risk} low-risk learner(s) with time to spare (anti-spam). "
        "Reminders are PREPARED only — a human approves before any are sent."
    )
    return ReminderPlan(
        assignment_id=assignment_id,
        reminders=reminders,
        skipped_submitted=skipped_submitted,
        skipped_low_risk=skipped_low_risk,
        rationale=rationale,
    )
