"""\"What do I need to do today\" synthesis (B9).

The dossier:

  it answers "what do I need to do today" from the user's role, timetable, tasks,
  permissions, and recent progress.

This synthesises a single, role-shaped "Today" view from five inputs:

  - **role** — student / teacher / parent / admin (shapes tone + ordering).
  - **timetable** — the day's scheduled items.
  - **tasks** — open/owned tasks and their due windows.
  - **permissions** — what the user is actually allowed to act on (a denied item
    is never surfaced as actionable; INVARIANT 3).
  - **progress** — recent progress signals that should prompt attention.

Two laws shape it:

  1. **Permission-aware (INVARIANT 3 + 8).** An item the user lacks permission to
     act on is NOT shown as an actionable item. Consequential actions (publish /
     send / grade / submit) are surfaced as "needs your approval" — recommend /
     prepare — never as something already done. Nothing on Today auto-fires.
  2. **Explainable + bounded.** Every line carries a plain-language WHY and is
     ordered by attention (overdue/approval first). It is a focused list of what
     needs attention now, not a wall of data.

Degrade-safe + deterministic: pure synthesis over the supplied inputs; no
provider, no secret, no live call.

Import-safe: no I/O, no provider, no secret value read at import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Literal

from .companion import CompanionRole


class TodayItemKind(str, Enum):
    SCHEDULE = "schedule"          # a timetabled item.
    TASK = "task"                  # an open owned task.
    APPROVAL = "approval"          # a consequential action awaiting approval.
    PROGRESS = "progress"          # a progress signal needing attention.


class Attention(IntEnum):
    """How urgently an item needs attention. Higher sorts first."""

    INFO = 0
    SOON = 1
    TODAY = 2
    OVERDUE = 3
    NEEDS_APPROVAL = 4   # a blocked consequential action — surfaced at the top.


# Consequential actions that must NEVER be auto-fired — they are surfaced as
# "needs your approval" on Today (permission ladder).
CONSEQUENTIAL_ACTIONS: frozenset[str] = frozenset(
    {"publish", "send", "grade", "submit", "approve", "release"}
)


@dataclass(frozen=True)
class TimetableItem:
    label: str
    at: str                # plain time/window label, e.g. "09:00 — period 1".


@dataclass(frozen=True)
class TaskItem:
    title: str
    due: str               # plain-language due, e.g. "today" / "overdue".
    # The action this task entails; if consequential it becomes an approval item.
    action: str = "review"
    overdue: bool = False


@dataclass(frozen=True)
class ProgressItem:
    label: str
    needs_attention: bool
    why: str


@dataclass(frozen=True)
class Permissions:
    """What the user may act on. A capability absent here is NOT actionable."""

    can: frozenset[str] = field(default_factory=frozenset)

    def allows(self, action: str) -> bool:
        return action in self.can


@dataclass(frozen=True)
class TodayItem:
    """One line on the Today view — explainable + attention-ranked."""

    kind: TodayItemKind
    headline: str
    why: str
    attention: Attention
    # True only for a consequential action awaiting approval (permission ladder).
    requires_approval: bool = False
    action: str | None = None


@dataclass
class TodayView:
    """The role-shaped Today view: a focused, ranked, explainable list."""

    role: CompanionRole
    items: tuple[TodayItem, ...]
    # Items omitted because the user lacks permission (explainability, not action).
    withheld_for_permission: tuple[str, ...] = field(default_factory=tuple)

    @property
    def approvals(self) -> tuple[TodayItem, ...]:
        return tuple(i for i in self.items if i.requires_approval)


_ROLE_GREETING: dict[CompanionRole, str] = {
    CompanionRole.STUDENT: "Here is what needs your attention today.",
    CompanionRole.TEACHER: "Here is your day — prepared for your review.",
    CompanionRole.PARENT: "Here is what is worth a moment today.",
    CompanionRole.ADMIN: "Here is what needs a decision today.",
}


class TodaySynthesizer:
    """Synthesises the role-shaped "Today" view from role + timetable + tasks +
    permissions + progress, permission-aware and approval-aware."""

    def greeting(self, role: CompanionRole) -> str:
        return _ROLE_GREETING.get(role, "Here is what needs your attention today.")

    def synthesise(
        self,
        *,
        role: CompanionRole,
        timetable: list[TimetableItem] | None = None,
        tasks: list[TaskItem] | None = None,
        permissions: Permissions | None = None,
        progress: list[ProgressItem] | None = None,
    ) -> TodayView:
        timetable = timetable or []
        tasks = tasks or []
        progress = progress or []
        perms = permissions or Permissions()

        items: list[TodayItem] = []
        withheld: list[str] = []

        # Timetable — informational schedule lines (acting on a slot is implicit).
        for t in timetable:
            items.append(
                TodayItem(
                    kind=TodayItemKind.SCHEDULE,
                    headline=f"{t.at}: {t.label}",
                    why="On your timetable today.",
                    attention=Attention.TODAY,
                )
            )

        # Tasks — permission-gated. A consequential action becomes an approval
        # item (never shown as done); an action the user can't perform is withheld.
        for task in tasks:
            is_consequential = task.action in CONSEQUENTIAL_ACTIONS
            if not perms.allows(task.action):
                withheld.append(
                    f"{task.title}: not shown as actionable — you do not have "
                    f"permission to {task.action} (ask an admin to grant it)."
                )
                continue
            if is_consequential:
                items.append(
                    TodayItem(
                        kind=TodayItemKind.APPROVAL,
                        headline=f"Awaiting your approval: {task.title}",
                        why=(
                            f"This requires you to {task.action} — a consequential "
                            "action that is prepared but never fired automatically."
                        ),
                        attention=Attention.NEEDS_APPROVAL,
                        requires_approval=True,
                        action=task.action,
                    )
                )
            else:
                items.append(
                    TodayItem(
                        kind=TodayItemKind.TASK,
                        headline=task.title,
                        why=f"Open task, due {task.due}.",
                        attention=Attention.OVERDUE if task.overdue else Attention.SOON,
                        action=task.action,
                    )
                )

        # Progress — only those flagged as needing attention.
        for p in progress:
            if not p.needs_attention:
                continue
            items.append(
                TodayItem(
                    kind=TodayItemKind.PROGRESS,
                    headline=p.label,
                    why=p.why,
                    attention=Attention.TODAY,
                )
            )

        # Rank by attention (highest first); stable for equal attention so input
        # order is preserved within a band.
        ranked = tuple(
            sorted(items, key=lambda i: int(i.attention), reverse=True)
        )
        return TodayView(
            role=role,
            items=ranked,
            withheld_for_permission=tuple(withheld),
        )
