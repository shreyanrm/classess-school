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

from .config import CommunicationSettings, get_settings
from .safeguarding import Escalation, SafetyFinding, Safeguard


class CompanionRole(str, Enum):
    """The companion is shaped to a role/stage. The shape changes the tone and
    the vocabulary, never the boundaries — the boundaries are identical for all."""

    EARLY_LEARNER = "early_learner"
    LEARNER = "learner"
    SENIOR_LEARNER = "senior_learner"


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
}

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
    ) -> None:
        self._role = role
        self._settings = settings or get_settings()
        # No unmonitored channel: the companion ALWAYS has a safeguard. If none
        # is supplied it constructs the deterministic on-device one.
        self._guard = guard or Safeguard(self._settings)

    @property
    def role(self) -> CompanionRole:
        return self._role

    @property
    def guard(self) -> Safeguard:
        return self._guard

    def respond(self, learner_text: str, *, writer_ref: str) -> CompanionReply:
        """The single entry point. Screen first, escalate serious matters, and
        otherwise return a bounded, boundary-checked, anti-dependence reply.

        ``writer_ref`` is the learner's opaque canonical_uuid (no PII).
        """
        finding, escalation = self._guard.screen(
            learner_text, surface="companion", writer_ref=writer_ref
        )

        # Serious matter -> the companion NEVER counsels. Hand off to a human.
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
        return CompanionReply(
            text=text,
            role=self._role,
            handed_off=False,
            escalation=None,
            finding=finding,
            points_to_people=True,
            source="scripted_bounded",
        )

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
        return f"{opener} {_TO_INDEPENDENCE} {_TO_PEOPLE}"
