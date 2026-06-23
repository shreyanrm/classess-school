"""Engagement / attention SIGNALS (d7) -- assistive only.

This module turns coarse, on-device, non-identifying observations into a few
*assistive* engagement signals that help a teacher pace a lesson. It is bound by
hard rules:

- Signals are ASSISTIVE and NEVER PUNITIVE. Nothing here produces a sanction,
  a score against a person, or a ranking of learners.
- Signals are NEVER IDENTITY-GRADED. They describe the room or an opaque
  subject's *moment-to-moment activity*, never a judgement of who someone is.
- Vision ASSISTS and NEVER grades from a face. Any vision-derived input must be
  an on-device, reduced descriptor (e.g. "screen-facing: yes/no") with
  ``from_face`` False. We refuse face-derived inputs.
- Generate-and-verify with a confidence gate: a signal below the gate is held
  back as ``UNCERTAIN`` rather than surfaced as fact.
- Only opaque ``canonical_uuid`` is referenced; no PII.

Inputs are deliberately coarse activity counters (board interactions, poll
participation, presence continuity). The output is a calm, plain-language band,
not a number to rank by.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional

from .events import Event, EventKind, is_opaque_uuid

#: Confidence gate below which a signal is reported as UNCERTAIN, not asserted.
ATTENTION_CONFIDENCE_GATE = 0.60


class EngagementBand(str, enum.Enum):
    """Calm, plain-language bands. Never a punitive label, never a rank."""

    ENGAGED = "engaged"
    SETTLING = "settling"
    NEEDS_A_NUDGE = "needs_a_nudge"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class ActivityWindow:
    """Coarse, non-identifying activity counts over a short window.

    All inputs are activity counters, not biometric or affective measures.
    ``screen_facing_hint`` is an OPTIONAL on-device descriptor; it must never be
    derived from a face (``from_face`` is validated elsewhere) and is only one
    weak input among several.
    """

    board_interactions: int = 0
    poll_responses: int = 0
    presence_continuity: float = 1.0  # fraction of window present, in [0, 1]
    window_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.board_interactions < 0 or self.poll_responses < 0:
            raise ValueError("activity counts cannot be negative")
        if not (0.0 <= self.presence_continuity <= 1.0):
            raise ValueError("presence_continuity must be in [0, 1]")


@dataclass(frozen=True)
class VisionAssist:
    """An on-device, non-face attention assist (optional, weak).

    Example: a device-local heuristic that the learner's screen is foregrounded.
    ``from_face`` must be False -- we never grade from a face.
    """

    screen_foregrounded: bool
    confidence: float
    from_face: bool = False

    def __post_init__(self) -> None:
        if self.from_face:
            raise ValueError(
                "attention vision must never be derived from a face"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True)
class AttentionSignal:
    """An assistive, non-punitive, non-identity-graded engagement signal."""

    subject_uuid: str
    band: EngagementBand
    confidence: float
    assistive: bool = True
    punitive: bool = False
    identity_graded: bool = False

    def __post_init__(self) -> None:
        if not is_opaque_uuid(self.subject_uuid):
            raise ValueError("subject_uuid must be an opaque canonical_uuid")
        if self.punitive:
            raise ValueError("attention signals are never punitive")
        if self.identity_graded:
            raise ValueError("attention signals are never identity-graded")
        if not self.assistive:
            raise ValueError("attention signals are assistive by definition")


def assess(
    subject_uuid: str,
    window: ActivityWindow,
    vision: Optional[VisionAssist] = None,
) -> AttentionSignal:
    """Produce one assistive engagement signal from coarse activity.

    Generate-and-verify: we compute a band and a confidence, then gate it. Below
    the confidence gate we return ``UNCERTAIN`` rather than assert a band. The
    result is advisory -- a teacher decides what, if anything, to do.
    """
    if not is_opaque_uuid(subject_uuid):
        raise ValueError("subject_uuid must be an opaque canonical_uuid")

    # Weak, transparent scoring over activity counters in [0, 1].
    interaction_score = min(1.0, window.board_interactions / 5.0)
    poll_score = min(1.0, window.poll_responses / 1.0)
    activity = (
        0.45 * interaction_score
        + 0.30 * poll_score
        + 0.25 * window.presence_continuity
    )

    # Vision is at most a small, optional nudge and only when confident.
    confidence = 0.55 + 0.30 * window.presence_continuity
    if vision is not None and vision.confidence >= ATTENTION_CONFIDENCE_GATE:
        if vision.screen_foregrounded:
            activity = min(1.0, activity + 0.10)
        confidence = min(1.0, confidence + 0.10)

    if confidence < ATTENTION_CONFIDENCE_GATE:
        band = EngagementBand.UNCERTAIN
    elif activity >= 0.66:
        band = EngagementBand.ENGAGED
    elif activity >= 0.33:
        band = EngagementBand.SETTLING
    else:
        band = EngagementBand.NEEDS_A_NUDGE

    return AttentionSignal(
        subject_uuid=subject_uuid,
        band=band,
        confidence=round(confidence, 3),
    )


def to_event(session_id: str, signal: AttentionSignal) -> Event:
    """Build an append-only engagement-signal event.

    The event is explicitly tagged assistive / non-punitive so downstream
    consumers cannot repurpose it as a sanction.
    """
    return Event(
        kind=EventKind.ENGAGEMENT_SIGNAL,
        session_id=session_id,
        subject_uuid=signal.subject_uuid,
        payload={
            "band": signal.band.value,
            "confidence": signal.confidence,
            "assistive": True,
            "punitive": False,
            "identity_graded": False,
        },
    )
