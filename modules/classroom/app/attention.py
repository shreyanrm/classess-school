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


# ---------------------------------------------------------------------------
# Raised-hand input + no-person-present signal (assistive teacher nudges).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RaisedHand:
    """A raised-hand input -- a learner asking to participate.

    May originate from an explicit tap OR from on-device gesture detection; in
    EITHER case it is a POSITIVE participation cue surfaced to the teacher, never
    a face grade. A vision-detected hand must NOT be face-derived (``from_face``
    False) and is gated like any other assist.
    """

    subject_uuid: str
    confidence: float = 1.0
    from_vision: bool = False
    from_face: bool = False

    def __post_init__(self) -> None:
        if not is_opaque_uuid(self.subject_uuid):
            raise ValueError("subject_uuid must be an opaque canonical_uuid")
        if self.from_face:
            raise ValueError("a raised hand is never derived from a face")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")

    @property
    def accepted(self) -> bool:
        """An explicit (non-vision) hand is always accepted; a vision-detected
        hand must clear the confidence gate (generate-and-verify)."""
        if not self.from_vision:
            return True
        return self.confidence >= ATTENTION_CONFIDENCE_GATE


def raised_hand_event(session_id: str, hand: RaisedHand) -> Optional[Event]:
    """Build an append-only raised-hand event, or None if a vision-detected hand
    failed the confidence gate (held back rather than asserted)."""
    if not hand.accepted:
        return None
    return Event(
        kind=EventKind.RAISED_HAND,
        session_id=session_id,
        subject_uuid=hand.subject_uuid,
        payload={
            "confidence": round(hand.confidence, 3),
            "from_vision": hand.from_vision,
            "assistive": True,
            "punitive": False,
        },
    )


@dataclass(frozen=True)
class NoPersonSignal:
    """A 'no person in front of the camera' signal for an online session.

    On-device only, NEVER face-derived: it reports the ABSENCE of any person in
    the camera frame, not the identity or affect of anyone. It is a gentle nudge
    to the teacher (the learner may have stepped away), NEVER attendance and
    NEVER a grade. Gated like any other assist.
    """

    subject_uuid: str
    confidence: float
    from_face: bool = False

    def __post_init__(self) -> None:
        if not is_opaque_uuid(self.subject_uuid):
            raise ValueError("subject_uuid must be an opaque canonical_uuid")
        if self.from_face:
            raise ValueError("a no-person signal is never derived from a face")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")

    @property
    def accepted(self) -> bool:
        return self.confidence >= ATTENTION_CONFIDENCE_GATE


def no_person_event(session_id: str, signal: NoPersonSignal) -> Optional[Event]:
    """Build an append-only no-person-present event, or None if below the gate.

    The event is explicitly assistive / non-punitive and is NOT attendance: it
    never marks a learner absent.
    """
    if not signal.accepted:
        return None
    return Event(
        kind=EventKind.NO_PERSON_PRESENT,
        session_id=session_id,
        subject_uuid=signal.subject_uuid,
        payload={
            "confidence": round(signal.confidence, 3),
            "assistive": True,
            "punitive": False,
            "is_attendance": False,
        },
    )


# ---------------------------------------------------------------------------
# Engagement <-> later-performance relation (correlation, never causation/grade).
# ---------------------------------------------------------------------------
#: Bands mapped to a coarse engagement level for correlation only.
_BAND_LEVEL = {
    EngagementBand.ENGAGED: 1.0,
    EngagementBand.SETTLING: 0.5,
    EngagementBand.NEEDS_A_NUDGE: 0.0,
}


@dataclass(frozen=True)
class EngagementPerformanceLink:
    """A topic-level relation between a learner's engagement and LATER performance.

    This relates an engagement band observed during a topic to a later
    performance score (e.g. on a quiz of that topic). It is descriptive evidence
    for a teacher -- "engagement was low on this topic and so was the later score"
    -- NEVER a grade of the person and NEVER a claim that engagement CAUSED the
    score. Held back as UNCERTAIN when engagement was uncertain.
    """

    subject_uuid: str
    topic_ref: str
    engagement_band: EngagementBand
    later_score: float  # [0, 1] performance on the topic, later
    relation: str  # plain-language, non-punitive description
    assistive: bool = True

    def __post_init__(self) -> None:
        if not is_opaque_uuid(self.subject_uuid):
            raise ValueError("subject_uuid must be an opaque canonical_uuid")
        if not self.topic_ref:
            raise ValueError("topic_ref is required")
        if not (0.0 <= self.later_score <= 1.0):
            raise ValueError("later_score must be in [0, 1]")


def relate_engagement_to_performance(
    subject_uuid: str,
    topic_ref: str,
    engagement_band: EngagementBand,
    later_score: float,
) -> EngagementPerformanceLink:
    """Relate an engagement band on a topic to a later performance score.

    Generate-and-verify: an UNCERTAIN engagement band yields an explicitly
    uncertain relation rather than a confident claim. The output is advisory.
    """
    if engagement_band is EngagementBand.UNCERTAIN:
        relation = "engagement was uncertain; no reliable relation to draw"
    else:
        level = _BAND_LEVEL[engagement_band]
        if level >= 0.5 and later_score >= 0.5:
            relation = "engaged on this topic and later performed well"
        elif level < 0.5 and later_score < 0.5:
            relation = (
                "low engagement on this topic and a lower later score -- "
                "a topic to revisit"
            )
        else:
            relation = "engagement and later score did not move together here"
    return EngagementPerformanceLink(
        subject_uuid=subject_uuid,
        topic_ref=topic_ref,
        engagement_band=engagement_band,
        later_score=later_score,
        relation=relation,
    )


@dataclass(frozen=True)
class TopicEngagementSummary:
    """A topic-level, roster-wide read of engagement vs. later performance.

    Aggregates many learners' :class:`EngagementPerformanceLink` for ONE topic into
    a calm teacher view: how many learners were engaged, how the cohort performed
    later, and whether the two moved together for the GROUP. It deliberately reports
    COUNTS and AVERAGES, never a per-learner ranking and never a verdict on a
    person; uncertain learners are excluded from the relation rather than guessed.
    """

    topic_ref: str
    learners: int
    uncertain: int
    avg_later_score: float
    cohort_relation: str
    assistive: bool = True

    def __post_init__(self) -> None:
        if not self.topic_ref:
            raise ValueError("topic_ref is required")
        if self.learners < 0 or self.uncertain < 0:
            raise ValueError("counts cannot be negative")


def summarise_topic_engagement(
    topic_ref: str, links: list[EngagementPerformanceLink]
) -> TopicEngagementSummary:
    """Aggregate per-learner engagement<->performance links for one topic.

    Generate-and-verify at the cohort level: learners whose engagement was
    UNCERTAIN are counted but excluded from the relation (never guessed into it).
    The relation is a plain-language, non-punitive read for the teacher about the
    GROUP, never a ranking of learners.
    """
    if not topic_ref:
        raise ValueError("topic_ref is required")
    confident = [
        ln for ln in links if ln.engagement_band is not EngagementBand.UNCERTAIN
    ]
    uncertain = len(links) - len(confident)
    avg_score = (
        round(sum(ln.later_score for ln in confident) / len(confident), 3)
        if confident
        else 0.0
    )
    if not confident:
        relation = "engagement was uncertain across the cohort; no reliable read"
    else:
        avg_level = sum(
            _BAND_LEVEL[ln.engagement_band] for ln in confident
        ) / len(confident)
        if avg_level >= 0.5 and avg_score >= 0.5:
            relation = "the class engaged with this topic and later performed well"
        elif avg_level < 0.5 and avg_score < 0.5:
            relation = (
                "low class engagement on this topic and lower later scores -- "
                "a topic to revisit with the group"
            )
        else:
            relation = "class engagement and later scores did not move together here"
    return TopicEngagementSummary(
        topic_ref=topic_ref,
        learners=len(links),
        uncertain=uncertain,
        avg_later_score=avg_score,
        cohort_relation=relation,
    )


def performance_link_event(
    session_id: str, link: EngagementPerformanceLink
) -> Event:
    """Build an append-only engagement<->performance relation event (assistive)."""
    return Event(
        kind=EventKind.ENGAGEMENT_PERFORMANCE_LINK,
        session_id=session_id,
        subject_uuid=link.subject_uuid,
        payload={
            "topic_ref": link.topic_ref,
            "engagement_band": link.engagement_band.value,
            "later_score": link.later_score,
            "relation": link.relation,
            "assistive": True,
            "punitive": False,
            "identity_graded": False,
        },
    )
