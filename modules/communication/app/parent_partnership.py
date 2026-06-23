"""Parent engagement & parent–teacher partnership (B9).

The dossier is unambiguous about the shape of this surface:

  Parent surface is partnership and pride, not surveillance. The Parent surface
  is consent-authority + partnership, never surveillance. CONSENT gates every
  cross-context read.

So this module does two things, both bounded:

  1. **Frames a child's progress as partnership and pride** — in the parent's
     language, in plain words (never a raw number or formula), with one or a few
     concrete things the parent can do WITH the child. It never surfaces
     minute-by-minute tracking, location, keystrokes, or a surveillance feed.
     The framing is structurally pride/partnership: a small set of vetted shapes.
  2. **Gates every cross-context read on consent** — a parent reading a child's
     behavioural/learning context is a CROSS-CONTEXT read. It does not proceed
     without a satisfied consent + purpose check (INVARIANT 6). No consent ->
     denied, fail-closed. The denial is honest and explains how to grant consent;
     it never leaks the data it withheld.

Surveillance is refused in code: a fixed deny-list of surveillance-shaped
purposes can never be read, even WITH a consent grant. Consent permits
partnership, never monitoring.

Import-safe: no I/O, no provider, no secret read at import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from .config import CommunicationSettings, get_settings


class ConsentError(PermissionError):
    """Raised when a cross-context read is attempted without satisfied consent.
    The read does not proceed and no withheld data is returned (INVARIANT 6)."""


class SurveillancePurposeError(PermissionError):
    """Raised when a read is attempted for a surveillance-shaped purpose. These
    are refused even with a consent grant — consent permits partnership, never
    monitoring. The Parent surface is never surveillance."""


# Purposes a parent read MAY be made for — all partnership/pride shaped.
PARTNERSHIP_PURPOSES: frozenset[str] = frozenset(
    {
        "partnership_summary",   # plain-language progress + how to help.
        "celebrate_progress",    # pride: a genuine win to acknowledge together.
        "support_at_home",       # one concrete thing to do WITH the child.
        "meeting_preparation",   # context for a parent–teacher conversation.
    }
)

# Purposes that are surveillance by shape. These are NEVER served — not even with
# a consent grant. The list is the wall.
SURVEILLANCE_PURPOSES: frozenset[str] = frozenset(
    {
        "live_location",
        "keystroke_log",
        "screen_monitoring",
        "minute_by_minute_activity",
        "message_surveillance",
        "continuous_tracking",
        "covert_monitoring",
    }
)


@dataclass(frozen=True)
class ConsentGrant:
    """A resolved consent grant for a parent reading a child's context.

    In production this is RESOLVED from the A1 consent authority through the
    gateway (INVARIANT 3 + 6). Here it is the value object that the resolver
    returns and the reader checks. Opaque refs only — no PII.
    """

    consent_ref: str           # the opaque consent record id stamped on reads.
    child_uuid: str            # whose context is being read (opaque).
    parent_uuid: str           # who is reading (opaque).
    purpose: str               # the granted purpose; must match the read.
    granted: bool
    # When the grant expires (ISO). Absent -> no time bound recorded.
    expires_at: str | None = None

    def is_valid_for(self, *, purpose: str, now: datetime | None = None) -> bool:
        if not self.granted:
            return False
        if self.purpose != purpose:
            return False
        if self.expires_at is not None:
            current = now or datetime.now(timezone.utc)
            try:
                exp = datetime.fromisoformat(self.expires_at)
            except ValueError:
                return False
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if current >= exp:
                return False
        return True


@dataclass
class PartnershipCard:
    """What a parent actually sees: pride + partnership, in plain language.

    No raw number, no formula, no surveillance feed. Carries the consent ref it
    was read under (auditability) and a 'why am I seeing this' line.
    """

    child_uuid: str
    headline: str            # a plain-language, pride-framed headline.
    a_genuine_win: str       # something real to celebrate together.
    one_thing_to_try: str    # one concrete thing to do WITH the child.
    why_you_see_this: str    # explainability — never surveillance.
    read_under_consent_ref: str
    purpose: str
    framing: Literal["partnership_and_pride"] = "partnership_and_pride"


# The plain-language shapes. Pride/partnership by construction; no raw metric.
_HEADLINES: dict[str, str] = {
    "partnership_summary": "Steady progress this fortnight, with one thing to do together.",
    "celebrate_progress": "A genuine win worth celebrating together.",
    "support_at_home": "One small thing at home would help right now.",
    "meeting_preparation": "A short, shared picture to bring to the meeting.",
}


class ParentPartnership:
    """The parent partnership surface. Frames pride/partnership and gates every
    cross-context read on consent — refusing surveillance outright."""

    def __init__(self, settings: CommunicationSettings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def settings(self) -> CommunicationSettings:
        return self._settings

    def _check_purpose(self, purpose: str) -> None:
        if purpose in SURVEILLANCE_PURPOSES:
            raise SurveillancePurposeError(
                f"Refusing a surveillance-shaped read ({purpose!r}). The Parent "
                "surface is partnership and pride, never surveillance — consent "
                "permits partnership, never monitoring."
            )
        if purpose not in PARTNERSHIP_PURPOSES:
            raise SurveillancePurposeError(
                f"Unknown read purpose {purpose!r}. Only partnership/pride purposes "
                f"are served: {sorted(PARTNERSHIP_PURPOSES)}."
            )

    def read_child_context(
        self,
        *,
        parent_uuid: str,
        child_uuid: str,
        purpose: str,
        consent: ConsentGrant | None,
        now: datetime | None = None,
    ) -> PartnershipCard:
        """Read a child's context for a parent — the CROSS-CONTEXT read.

        Order of walls:
          1. The purpose must be partnership/pride (surveillance refused outright,
             even with consent).
          2. A satisfied consent grant for THIS parent, THIS child, THIS purpose
             must be present and unexpired (INVARIANT 6). No consent -> denied,
             fail-closed, nothing leaked.
        """
        # Wall 1: never surveillance, even with consent.
        self._check_purpose(purpose)

        # Wall 2: consent gates the read. Fail-closed.
        if consent is None or not consent.granted:
            raise ConsentError(
                "Cross-context read denied: no consent on file for this parent to "
                "read this child's context. Ask the consent authority to grant "
                f"the {purpose!r} purpose first; nothing is shown until then."
            )
        if consent.child_uuid != child_uuid or consent.parent_uuid != parent_uuid:
            raise ConsentError(
                "Cross-context read denied: the consent grant does not match this "
                "parent and child. Nothing is shown."
            )
        if not consent.is_valid_for(purpose=purpose, now=now):
            raise ConsentError(
                "Cross-context read denied: the consent grant does not cover this "
                f"purpose ({purpose!r}) or has expired. Nothing is shown."
            )

        # Consent satisfied — return the pride/partnership framing (plain words).
        return PartnershipCard(
            child_uuid=child_uuid,
            headline=_HEADLINES.get(purpose, _HEADLINES["partnership_summary"]),
            a_genuine_win=(
                "Your child showed real persistence this week — they kept going "
                "through the parts that were hard."
            ),
            one_thing_to_try=(
                "Ask them to teach you one thing they learned. Explaining it back "
                "is how it sticks — and it is a lovely few minutes together."
            ),
            why_you_see_this=(
                "You are seeing this because you are this child's parent and you "
                "granted the partnership view. This is a shared picture to act on "
                "together — never a monitoring feed."
            ),
            read_under_consent_ref=consent.consent_ref,
            purpose=purpose,
        )
