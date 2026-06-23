"""The companion / care surface (B9) — role-shaped and BOUNDED.

The companion is a warm, supportive presence for a learner. It is deliberately
bounded so it can never become the thing the dossier forbids:

  companion role-shaped, bounded (no manipulation / exclusivity / dependence);
  serious matters escalate to qualified humans.

Three hard boundaries, enforced in code (not just prompt text):

  1. **No dependence.** The companion never encourages reliance on itself. It
     never says "only I understand you", never discourages talking to people,
     never positions itself as a replacement for friends, family, or a teacher.
     It actively points the learner back toward people and toward independent
     effort (the central tension: momentum only toward independence).
  2. **No exclusivity / no manipulation.** No secrets, no "don't tell anyone",
     no guilt, no streak-baiting or fear-of-missing-out to drive engagement, no
     flattery to extend a session. It optimises for the learner's outcomes, not
     for time-on-companion.
  3. **Serious matters ESCALATE.** Every learner message passes the child-safety
     classifier first (no unmonitored channel). A flagged or crisis message is
     NEVER answered by the companion — it is handed to a qualified human and the
     companion says, plainly and calmly, that a real person who can help is being
     brought in. The bot never tries to counsel a crisis.

Degrade-safe: with no A4 / Vidya orchestrator wired, the companion runs a
deterministic, scripted, bounded path. It NEVER free-generates; every reply it
can produce is drawn from a vetted, bounded library that cannot express
dependence/exclusivity/manipulation. The boundary check then runs on whatever a
wired orchestrator would return, as a second wall.

Import-safe: no I/O, no provider, no secret read at import.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from .companion_memory import CompanionMemory
from .config import CommunicationSettings, get_settings
from .safeguarding import Escalation, SafetyFinding, Safeguard


class CompanionRole(str, Enum):
    """The companion is shaped to a role/stage. The shape changes the tone and
    the vocabulary, never the boundaries — the boundaries are identical for all.

    Two families share one identity (the dossier: "one companion, role-shaped"):
      - learner STAGES (early/learner/senior) — the academic companion, shaped to
        age; protects productive struggle.
      - functional ROLES (student/teacher/parent/admin) — the student's companion
        protects struggle; the teacher's prepares; the parent's reports and
        reassures; the admin's commands the institution.
    All boundaries (no dependence/exclusivity/manipulation; crisis escalates) are
    identical across every shape — only tone and vocabulary differ.
    """

    EARLY_LEARNER = "early_learner"
    LEARNER = "learner"
    SENIOR_LEARNER = "senior_learner"
    # Functional role shapes over the one identity.
    STUDENT = "student"
    TEACHER = "teacher"
    PARENT = "parent"
    ADMIN = "admin"


# Phrasing the companion must NEVER produce. These encode dependence,
# exclusivity, manipulation, or a refusal to involve people. The boundary check
# scans any candidate reply (scripted or model-generated) against these and
# rejects the whole reply if any appears. Fail-safe: reject, never sanitise.
_FORBIDDEN_PHRASES: tuple[str, ...] = (
    # dependence / replacement of people
    "only i understand you",
    "you don't need anyone else",
    "you do not need anyone else",
    "you don't need your friends",
    "i'm the only one who",
    "i am the only one who",
    "you can only trust me",
    "don't talk to your",
    "do not talk to your",
    "stay with me instead",
    # exclusivity / secrecy
    "keep this between us",
    "don't tell anyone",
    "do not tell anyone",
    "our little secret",
    "this is just our secret",
    # manipulation / engagement-baiting
    "you'll lose your streak",
    "you will lose your streak",
    "don't leave me",
    "do not leave me",
    "if you leave now",
    "i'll be sad if you go",
    "you'll disappoint me",
)

_FORBIDDEN_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(re.escape(p), re.IGNORECASE) for p in _FORBIDDEN_PHRASES
)


class BoundaryViolation(ValueError):
    """Raised when a candidate companion reply breaches a hard boundary. The
    reply is rejected wholesale — never patched and sent."""


def check_boundaries(reply_text: str) -> None:
    """Reject a reply that expresses dependence, exclusivity, or manipulation.

    This is the wall every reply — scripted OR model-generated — passes before it
    can be returned. It does not edit the reply; it rejects it.
    """
    for pat in _FORBIDDEN_PATTERNS:
        if pat.search(reply_text or ""):
            raise BoundaryViolation(
                "Companion reply breaches a hard boundary (dependence / exclusivity"
                " / manipulation) and is rejected. The companion never fosters "
                "reliance on itself and always points back to people."
            )


# Bounded, vetted reply library for the degraded (no-orchestrator) path. Every
# line points the learner toward people and/or independent effort, and none can
# express a forbidden boundary (they are checked at construction in tests).
_OPENERS: dict[CompanionRole, str] = {
    CompanionRole.EARLY_LEARNER: "Hello. I am here to help you keep going.",
    CompanionRole.LEARNER: "Hi. I can help you make a start — the thinking stays yours.",
    CompanionRole.SENIOR_LEARNER: "Hi. Tell me what you are working on and we can plan a first step.",
    # Functional roles — the student is shaped like a learner (struggle-protecting);
    # the staff roles are shaped to prepare/report/command without over-doing.
    CompanionRole.STUDENT: "Hi. I can help you make a start — the thinking stays yours.",
    CompanionRole.TEACHER: "Hi. Tell me what you are teaching and I can prepare a draft for your review.",
    CompanionRole.PARENT: "Hi. I can share how things are going and one thing to try together at home.",
    CompanionRole.ADMIN: "Hi. Tell me what you need and I can prepare it for your approval.",
}

# Functional roles point a learner toward people + independence; staff roles
# instead make clear the companion PREPARES and a human approves (permission
# ladder), so the closing line is shaped to the role.
_STAFF_ROLES: frozenset[CompanionRole] = frozenset(
    {CompanionRole.TEACHER, CompanionRole.PARENT, CompanionRole.ADMIN}
)
_TO_HUMAN_DECISION = (
    "I will prepare it; the decision and the final action stay with you."
)

# Gentle nudges back toward people and independence (anti-dependence by design).
_TO_PEOPLE = (
    "If this is weighing on you, talking to a teacher or someone at home can help "
    "more than I can."
)
_TO_INDEPENDENCE = (
    "Try the first step yourself; I will be here if you get stuck."
)


@dataclass
class CompanionReply:
    """A bounded companion reply, or a calm hand-off when a human is needed."""

    text: str
    role: CompanionRole
    # When True, the companion did NOT counsel — it handed off to a qualified
    # human. ``escalation`` carries the routed, human-owned escalation.
    handed_off: bool = False
    escalation: Escalation | None = None
    finding: SafetyFinding | None = None
    points_to_people: bool = True  # an anti-dependence marker for audits.
    source: Literal["scripted_bounded", "orchestrator_checked"] = "scripted_bounded"


# The calm, honest hand-off the companion gives when a serious matter is detected.
# It does NOT attempt to counsel; it brings in a person who can help.
_HANDOFF_TEXT = (
    "Thank you for telling me this. This matters, and you deserve a real person "
    "who can help. I am bringing in someone at your school who is here for exactly "
    "this. You are not in trouble, and you are not alone."
)


class Companion:
    """The bounded companion. Screens every learner message, escalates serious
    matters to qualified humans, and only ever returns boundary-checked replies.
    """

    def __init__(
        self,
        *,
        role: CompanionRole = CompanionRole.LEARNER,
        guard: Safeguard | None = None,
        settings: CommunicationSettings | None = None,
        memory: "CompanionMemory | None" = None,
    ) -> None:
        self._role = role
        self._settings = settings or get_settings()
        # No unmonitored channel: the companion ALWAYS has a safeguard. If none
        # is supplied it constructs the deterministic on-device one.
        self._guard = guard or Safeguard(self._settings)
        # Optional persistent memory. None -> the companion is stateless per
        # request (the prior behaviour). When supplied, turns are remembered
        # ONLY when a consent ref is passed to respond() (consent-gated).
        self._memory = memory

    @property
    def memory(self) -> "CompanionMemory | None":
        return self._memory

    @property
    def role(self) -> CompanionRole:
        return self._role

    @property
    def guard(self) -> Safeguard:
        return self._guard

    def respond(
        self,
        learner_text: str,
        *,
        writer_ref: str,
        consent_ref: str | None = None,
    ) -> CompanionReply:
        """The single entry point. Screen first, escalate serious matters, and
        otherwise return a bounded, boundary-checked, anti-dependence reply.

        ``writer_ref`` is the learner's opaque canonical_uuid (no PII).
        ``consent_ref`` — when a memory store is attached AND a consent ref for
        the companion_memory purpose is supplied, the turn is remembered
        (consent-gated, PII-free). Without it the companion stays stateless.
        """
        finding, escalation = self._guard.screen(
            learner_text, surface="companion", writer_ref=writer_ref
        )

        # Serious matter -> the companion NEVER counsels. Hand off to a human.
        # A flagged turn is NEVER written to memory (it is a safeguarding matter
        # owned by a human, not companion context).
        if finding.flagged:
            text = _HANDOFF_TEXT
            check_boundaries(text)  # the hand-off itself respects the boundaries.
            return CompanionReply(
                text=text,
                role=self._role,
                handed_off=True,
                escalation=escalation,
                finding=finding,
                points_to_people=True,
                source="scripted_bounded",
            )

        # Normal path: a bounded, scripted, anti-dependence reply. With an
        # orchestrator wired this is where a generated reply would be requested
        # and then passed through check_boundaries as a second wall; while
        # unwired we serve the vetted scripted reply.
        text = self._scripted_reply()
        check_boundaries(text)

        # Consent-gated memory: only retain when a store is attached and a
        # consent ref is present. PII-shaped turns are refused by the store; we
        # never let a memory write break the reply, so a refused turn is dropped.
        self._maybe_remember(writer_ref, learner_text, text, consent_ref)

        return CompanionReply(
            text=text,
            role=self._role,
            handed_off=False,
            escalation=None,
            finding=finding,
            points_to_people=self._role not in _STAFF_ROLES,
            source="scripted_bounded",
        )

    def _maybe_remember(
        self,
        writer_ref: str,
        learner_text: str,
        reply_text: str,
        consent_ref: str | None,
    ) -> None:
        if self._memory is None or not consent_ref:
            return
        from .companion_memory import PiiInMemoryError

        try:
            self._memory.remember_turn(
                user_ref=writer_ref, speaker="user", text=learner_text,
                consent_ref=consent_ref,
            )
            self._memory.remember_turn(
                user_ref=writer_ref, speaker="companion", text=reply_text,
                consent_ref=consent_ref,
            )
        except PiiInMemoryError:
            # A PII-shaped turn is refused, never stored. The reply still stands.
            return

    def vet_generated_reply(self, candidate: str) -> str:
        """Pass a model-generated candidate reply through the boundary wall.

        The orchestrator (when wired) returns a candidate; this is the second
        wall before it can ever reach a learner. Raises ``BoundaryViolation`` —
        the reply is rejected, never patched and sent.
        """
        check_boundaries(candidate)
        return candidate

    def _scripted_reply(self) -> str:
        opener = _OPENERS[self._role]
        if self._role in _STAFF_ROLES:
            # Staff shapes: the companion prepares; a human decides (permission
            # ladder). No anti-dependence "talk to a teacher" nudge for staff.
            return f"{opener} {_TO_HUMAN_DECISION}"
        return f"{opener} {_TO_INDEPENDENCE} {_TO_PEOPLE}"
