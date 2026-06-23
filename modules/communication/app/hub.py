"""The communication hub (B9) — messages that become routed, owned, tracked tasks.

The dossier:

  Messages can become routed, owned, tracked tasks. Consent-gated. CHILD-SAFETY
  runs on every free-text surface.

So the hub does three things:

  1. **Screens every free-text message** through the child-safety subsystem
     before it is admitted. There is no unmonitored channel — a message is only
     created via :meth:`post`, which always screens. A flagged message is
     admitted but carries its escalation to a qualified human (the message is not
     silently dropped; safety routes it to a person).
  2. **Routes a message into a tracked task** — a message can be promoted into a
     task with an OWNER (a role + opaque ref), a due date, a status, and a why.
     The task is the trackable unit; its lifecycle is explicit (open ->
     in_progress -> done), never silently auto-closed.
  3. **Gates cross-context routing on consent** — routing a message ABOUT one
     person to a different context (e.g. a parent thread about a child) is a
     cross-context action and requires a satisfied consent ref (INVARIANT 6).

Sending/closing as consequential actions sit on the permission ladder: the hub
PREPARES routes and tasks; a human owns and advances them. Nothing
consequential auto-fires.

Import-safe: no I/O, no provider, no secret read at import.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from .config import CommunicationSettings, get_settings
from .safeguarding import Escalation, SafetyFinding, Safeguard


class TaskStatus(str, Enum):
    """Explicit, human-advanced task lifecycle. Never auto-closed by the system."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class ConsentError(PermissionError):
    """Raised when a cross-context route is attempted without a consent ref."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Message:
    """A free-text message in the hub. Always screened before admission.

    Carries opaque refs only. The safety finding is attached so downstream
    surfaces know whether a qualified human is already involved.
    """

    message_id: str
    surface: str
    sender_ref: str            # opaque canonical_uuid.
    context_ref: str           # the thread/context this belongs to (opaque).
    body: str                  # the free text (stays in the monitored store).
    posted_at: str
    finding: SafetyFinding
    escalation: Escalation | None = None

    @property
    def is_flagged(self) -> bool:
        return self.finding.flagged

    @property
    def needs_human(self) -> bool:
        return self.finding.requires_human


@dataclass
class RoutedTask:
    """A message promoted into an owned, tracked task. The trackable unit.

    Mirrors the A5 recommendation/approval shape: owner, due date, why,
    consequence-of-ignoring, status. Advanced only by a human (permission ladder).
    """

    task_id: str
    from_message_id: str
    title: str                 # a short, plain-language task title.
    owner_role: str            # who is responsible (a role).
    owner_ref: str             # the opaque ref of the responsible human.
    why: str                   # why this task exists (explainability).
    due_date: str | None
    status: TaskStatus = TaskStatus.OPEN
    created_at: str = field(default_factory=_now_iso)
    # If the underlying message was a safety flag, the task inherits it so the
    # qualified human owns BOTH the task and the safety escalation.
    safety_escalation: Escalation | None = None

    def advance(self, to: TaskStatus, *, by: str | None) -> "RoutedTask":
        """Advance the task — a human-owned action (permission ladder).

        Refuses without a ``by`` ref: advancing/closing a tracked task is
        consequential and never auto-fires (INVARIANT 8). The system prepares;
        a person advances.
        """
        if not by:
            raise PermissionError(
                "Advancing a tracked task is consequential and requires a human "
                "actor (by). The hub prepares tasks; it never closes them itself."
            )
        self.status = to
        return self


class CommunicationHub:
    """The hub: screen, post, route into tracked tasks, consent-gate cross-context.

    Every message ingress passes the safeguard — there is no path that posts an
    unscreened message. Tasks are owned by humans and advanced by humans.
    """

    def __init__(
        self,
        *,
        guard: Safeguard | None = None,
        settings: CommunicationSettings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        # No unmonitored channel: the hub ALWAYS has a safeguard.
        self._guard = guard or Safeguard(self._settings)
        self._messages: list[Message] = []
        self._tasks: list[RoutedTask] = []

    @property
    def guard(self) -> Safeguard:
        return self._guard

    def messages(self) -> list[Message]:
        return list(self._messages)

    def tasks(self) -> list[RoutedTask]:
        return list(self._tasks)

    def post(
        self,
        *,
        surface: str,
        sender_ref: str,
        context_ref: str,
        body: str,
    ) -> Message:
        """Post a free-text message — ALWAYS screened first (no unmonitored
        channel). A flagged message is admitted WITH its escalation attached so a
        qualified human is routed in; it is never silently dropped or hidden.
        """
        finding, escalation = self._guard.screen(
            body, surface=surface, writer_ref=sender_ref
        )
        message = Message(
            message_id=str(uuid.uuid4()),
            surface=surface,
            sender_ref=sender_ref,
            context_ref=context_ref,
            body=body,
            posted_at=_now_iso(),
            finding=finding,
            escalation=escalation,
        )
        self._messages.append(message)
        return message

    def route_to_task(
        self,
        message: Message,
        *,
        title: str,
        owner_role: str,
        owner_ref: str,
        why: str,
        due_date: str | None = None,
        target_context_ref: str | None = None,
        consent_ref: str | None = None,
    ) -> RoutedTask:
        """Promote a message into an owned, tracked task.

        If the task routes the message to a DIFFERENT context than the one it was
        posted in (a cross-context route, e.g. into a parent thread about a
        child), a consent ref is required (INVARIANT 6) — fail-closed.

        A safety-flagged message carries its escalation onto the task so the
        qualified human owns both.
        """
        is_cross_context = (
            target_context_ref is not None and target_context_ref != message.context_ref
        )
        if is_cross_context and not consent_ref:
            raise ConsentError(
                "Cross-context routing denied: routing this message into a "
                "different context requires a satisfied consent ref. Nothing is "
                "routed until consent is on file."
            )
        if not owner_ref:
            raise ValueError(
                "A routed task must have a human owner (owner_ref). The hub never "
                "creates an ownerless task."
            )
        task = RoutedTask(
            task_id=str(uuid.uuid4()),
            from_message_id=message.message_id,
            title=title,
            owner_role=owner_role,
            owner_ref=owner_ref,
            why=why,
            due_date=due_date,
            safety_escalation=message.escalation,
        )
        self._tasks.append(task)
        return task
