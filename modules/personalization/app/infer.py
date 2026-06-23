"""Implicit profiling — infer a personalization profile from behaviour.

The "get to know the user WITHOUT asking" engine. It derives a provisional
personalization profile (interests, preferred subjects, goal, pace, strengths,
preferred learning style) from BEHAVIOURAL SIGNALS and light onboarding CHOICES
— **never from an explicit questionnaire**. There is no place in this module to
pass questionnaire answers; the engine works from signals alone.

Hard rules honoured here:

  - NO QUESTIONNAIRE. Inputs are behavioural ``Signal``s (events, topic
    engagement, attempts) and light ``OnboardingChoice``s (a tap on a subject
    card, a picked goal-shaped option). Nothing accepts a free-text answer to a
    "what kind of learner are you" question.
  - EVIDENCE + CONFIDENCE ON EVERY TRAIT. Each inferred trait links to the
    signal ids that produced it and carries a confidence in [0, 1]. A trait with
    no evidence cannot exist.
  - PROVISIONAL, NEVER PERMANENT. A trait is a current best read, re-derivable
    from fresh signal. It is never a hardened label; ``provisional`` is always
    True and the projection re-infers from scratch on new signal (idempotent).
  - CONSENT + AGE-TIER GATED. Every trait is checked against the consent +
    age-tier gate before it is populated. An over-tier trait is silently
    OMITTED from a normal inference (the door does not exist), and the confidence
    is capped by the tier ceiling.
  - PII-FREE. Keyed by opaque ``canonical_uuid`` and opaque ontology ids only;
    signals carry no name/email/free-text-about-a-person.

This module does NOT author mastery (a spine concern). It reads behavioural
signals — including light mastery-shaped reads handed to it — and composes a
personalization read on top.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, Literal, Mapping

from .consent_gate import (
    PersonalizationConsent,
    TraitKind,
    effective_max_confidence,
    evaluate_inference,
    permitted_traits,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SignalKind(str, Enum):
    """The kinds of BEHAVIOURAL signal the engine reads.

    Every one of these is something the learner DID — an action, a dwell, an
    attempt — not something the learner was ASKED. There is intentionally no
    ``questionnaire_answer`` kind.
    """

    TOPIC_ENGAGEMENT = "topic_engagement"   # opened/dwelled on a topic
    ATTEMPT = "attempt"                      # attempted an item (independent/supported)
    CONTENT_INTERACTION = "content_interaction"  # interacted with a content format
    SESSION_RHYTHM = "session_rhythm"        # pace/cadence of a session
    CHOICE = "choice"                        # a light onboarding tap/selection


# Content formats a learner can interact with — feeds the learning-style read.
# These are behavioural format affinities, not a self-described "style".
ContentFormat = Literal["video", "reading", "interactive", "audio", "worked_example"]


@dataclass(frozen=True)
class Signal:
    """One behavioural signal. PII-free; keyed by opaque ids only.

    ``signal_id`` is the opaque event id used as evidence lineage on any trait it
    contributes to. ``subject_id`` is the topic/subject/ontology node the signal
    is about (opaque). ``weight`` lets stronger evidence (e.g. a long dwell, an
    independent correct attempt) count for more than a glance.
    """

    signal_id: str
    kind: SignalKind
    subject_id: str | None = None             # opaque ontology node (topic/subject)
    occurred_at: datetime | None = None
    weight: float = 1.0
    # Behavioural attributes — all derived from what happened, never asked.
    correct: bool | None = None
    independent: bool | None = None           # True = unaided attempt
    content_format: ContentFormat | None = None
    dwell_ms: int | None = None
    # A coarse, learner-action label for a CHOICE signal (e.g. tapped a subject
    # card, picked a goal-shaped option). Never free text about the person.
    choice_kind: Literal["subject", "goal", "pace"] | None = None
    choice_value: str | None = None           # opaque/enumerated option value


@dataclass(frozen=True)
class OnboardingChoice:
    """A light onboarding choice — a tap, not a questionnaire answer.

    The learner picked an option card during onboarding (a subject they like the
    look of, a goal-shaped option, a pace). This is a single low-friction
    selection, NOT a battery of profiling questions. It is converted to a
    ``Signal`` of kind CHOICE.
    """

    choice_id: str
    kind: Literal["subject", "goal", "pace"]
    value: str                                # enumerated option value, opaque
    occurred_at: datetime | None = None

    def to_signal(self) -> Signal:
        return Signal(
            signal_id=self.choice_id,
            kind=SignalKind.CHOICE,
            subject_id=self.value if self.kind == "subject" else None,
            occurred_at=self.occurred_at,
            weight=1.0,
            choice_kind=self.kind,
            choice_value=self.value,
        )


@dataclass(frozen=True)
class InferredTrait:
    """One inferred trait of the personalization profile.

    Carries its KIND, its VALUE (an opaque/enumerated read), the EVIDENCE that
    produced it (signal ids — never empty), a CONFIDENCE in [0, 1], and a
    plain-language EXPLANATION ("inferred because…") for transparency. It is
    always ``provisional`` — a current best read, never a permanent label.
    """

    kind: TraitKind
    value: str
    confidence: float
    evidence_signal_ids: tuple[str, ...]
    explanation: str
    provisional: bool = True
    inferred_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.evidence_signal_ids:
            raise ValueError(
                "An inferred trait must link to at least one evidence signal — "
                "no trait exists without evidence."
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("Trait confidence must be in [0, 1].")
        if not self.provisional:
            raise ValueError(
                "Inferred traits are always provisional — a trait is never a "
                "permanent label."
            )
        if not self.explanation:
            raise ValueError(
                "An inferred trait must carry a plain-language explanation "
                "('inferred because…') for transparency."
            )


@dataclass(frozen=True)
class InferenceInput:
    """Everything the engine needs to infer a profile — signals only.

    There is no questionnaire field anywhere on this object. Onboarding choices
    are light taps, converted to signals.
    """

    subject: str                              # opaque canonical_uuid of the learner
    signals: tuple[Signal, ...] = ()
    onboarding_choices: tuple[OnboardingChoice, ...] = ()

    def all_signals(self) -> tuple[Signal, ...]:
        return self.signals + tuple(c.to_signal() for c in self.onboarding_choices)


@dataclass(frozen=True)
class InferredProfile:
    """The inferred personalization profile for one learner.

    A flat set of inferred traits, each gated, evidenced, confident, and
    provisional. ``denied_traits`` records (trait kind -> plain-language reason)
    for kinds the consent/age-tier gate refused — kept for transparency so a
    surface can explain "we do not infer this for you", never as a populated
    value.
    """

    subject: str
    traits: tuple[InferredTrait, ...]
    inferred_at: datetime
    denied_traits: tuple[tuple[str, str], ...] = ()

    def trait(self, kind: TraitKind) -> InferredTrait | None:
        for t in self.traits:
            if t.kind == kind:
                return t
        return None

    def traits_of(self, kind: TraitKind) -> tuple[InferredTrait, ...]:
        return tuple(t for t in self.traits if t.kind == kind)


# ---------------------------------------------------------------------------
# Confidence shaping
# ---------------------------------------------------------------------------

def _confidence_from_weight(total_weight: float) -> float:
    """A saturating curve: more corroborating evidence -> higher confidence, with
    diminishing returns and never reaching certainty. A single light signal lands
    low; sustained behaviour climbs but plateaus. Never returns >= 1.0 (a trait is
    never certain) and never returns 0 for a present signal.
    """
    if total_weight <= 0:
        return 0.0
    # 1 - 2^(-w/2): w=1 -> ~0.29, w=3 -> ~0.65, w=6 -> ~0.875, asymptote 1.
    return 1.0 - 2.0 ** (-total_weight / 2.0)


def _cap(value: float, ceiling: float) -> float:
    return min(value, ceiling)


# ---------------------------------------------------------------------------
# Per-trait inference rules (behavioural only)
# ---------------------------------------------------------------------------

def _aggregate_by_subject(
    signals: Iterable[Signal], kinds: set[SignalKind]
) -> dict[str, tuple[float, list[str]]]:
    """Sum weight per opaque subject_id for signals of the given kinds."""
    acc: dict[str, tuple[float, list[str]]] = defaultdict(lambda: (0.0, []))
    for s in signals:
        if s.kind not in kinds or not s.subject_id:
            continue
        w, ids = acc[s.subject_id]
        acc[s.subject_id] = (w + max(s.weight, 0.0), ids + [s.signal_id])
    return dict(acc)


def _infer_interest(signals: list[Signal], cap: float) -> list[InferredTrait]:
    """Interests: the topics/subjects the learner keeps returning to.

    Behavioural only — engagement, content interaction, and subject choices. The
    strongest one or two by accumulated weight become interest traits.
    """
    agg = _aggregate_by_subject(
        signals,
        {SignalKind.TOPIC_ENGAGEMENT, SignalKind.CONTENT_INTERACTION, SignalKind.CHOICE},
    )
    ranked = sorted(agg.items(), key=lambda kv: kv[1][0], reverse=True)
    out: list[InferredTrait] = []
    for subject_id, (weight, ids) in ranked[:2]:
        conf = _cap(_confidence_from_weight(weight), cap)
        out.append(
            InferredTrait(
                kind=TraitKind.INTEREST,
                value=subject_id,
                confidence=conf,
                evidence_signal_ids=tuple(ids),
                explanation=(
                    "inferred because the learner repeatedly engaged with this "
                    "area through their own actions"
                ),
            )
        )
    return out


def _infer_preferred_subject(signals: list[Signal], cap: float) -> list[InferredTrait]:
    """Preferred subject: the single subject with the most engagement+attempts."""
    agg = _aggregate_by_subject(
        signals,
        {SignalKind.TOPIC_ENGAGEMENT, SignalKind.ATTEMPT, SignalKind.CHOICE},
    )
    if not agg:
        return []
    subject_id, (weight, ids) = max(agg.items(), key=lambda kv: kv[1][0])
    conf = _cap(_confidence_from_weight(weight), cap)
    return [
        InferredTrait(
            kind=TraitKind.PREFERRED_SUBJECT,
            value=subject_id,
            confidence=conf,
            evidence_signal_ids=tuple(ids),
            explanation=(
                "inferred because this subject drew the most of the learner's "
                "time and attempts"
            ),
        )
    ]


def _infer_pace(signals: list[Signal], cap: float) -> list[InferredTrait]:
    """Pace: from session rhythm and time-on-attempt — fast/steady/deliberate."""
    rhythm = [s for s in signals if s.kind in {SignalKind.SESSION_RHYTHM, SignalKind.ATTEMPT}]
    dwell = [s.dwell_ms for s in rhythm if s.dwell_ms is not None]
    if not dwell:
        return []
    avg = sum(dwell) / len(dwell)
    if avg < 20_000:
        value = "fast"
    elif avg < 60_000:
        value = "steady"
    else:
        value = "deliberate"
    weight = float(len(dwell))
    conf = _cap(_confidence_from_weight(weight), cap)
    ids = tuple(s.signal_id for s in rhythm if s.dwell_ms is not None)
    return [
        InferredTrait(
            kind=TraitKind.PACE,
            value=value,
            confidence=conf,
            evidence_signal_ids=ids,
            explanation=(
                "inferred from the rhythm of the learner's sessions and how long "
                "they spend per item"
            ),
        )
    ]


def _infer_goal(signals: list[Signal], cap: float) -> list[InferredTrait]:
    """Goal: from goal-shaped onboarding taps and sustained focus on an area.

    A light onboarding goal-tap is the clearest signal; absent that, a strongly
    dominant subject focus is read as a working goal.
    """
    goal_choices = [s for s in signals if s.choice_kind == "goal" and s.choice_value]
    if goal_choices:
        weight = sum(max(s.weight, 0.0) for s in goal_choices)
        conf = _cap(_confidence_from_weight(weight), cap)
        return [
            InferredTrait(
                kind=TraitKind.GOAL,
                value=goal_choices[-1].choice_value or "",
                confidence=conf,
                evidence_signal_ids=tuple(s.signal_id for s in goal_choices),
                explanation=(
                    "inferred because the learner picked this goal-shaped option "
                    "during onboarding"
                ),
            )
        ]
    return []


def _infer_strength(signals: list[Signal], cap: float) -> list[InferredTrait]:
    """Strength: areas where INDEPENDENT attempts are reliably correct.

    The independence flag is the keystone — performing well WITH help is not a
    strength. Only independent+correct attempts count.
    """
    acc: dict[str, tuple[float, list[str]]] = defaultdict(lambda: (0.0, []))
    for s in signals:
        if s.kind != SignalKind.ATTEMPT or not s.subject_id:
            continue
        if s.correct and s.independent:
            w, ids = acc[s.subject_id]
            acc[s.subject_id] = (w + max(s.weight, 0.0), ids + [s.signal_id])
    if not acc:
        return []
    out: list[InferredTrait] = []
    ranked = sorted(acc.items(), key=lambda kv: kv[1][0], reverse=True)
    for subject_id, (weight, ids) in ranked[:2]:
        conf = _cap(_confidence_from_weight(weight), cap)
        out.append(
            InferredTrait(
                kind=TraitKind.STRENGTH,
                value=subject_id,
                confidence=conf,
                evidence_signal_ids=tuple(ids),
                explanation=(
                    "inferred because the learner handled this reliably on their "
                    "own, without help"
                ),
            )
        )
    return out


def _infer_learning_style(signals: list[Signal], cap: float) -> list[InferredTrait]:
    """Learning style: the content FORMAT the learner returns to most.

    The deepest inference, gated to the adult tier only. Read from format-tagged
    content interactions — what the learner actually re-used, never asked.
    """
    acc: dict[str, tuple[float, list[str]]] = defaultdict(lambda: (0.0, []))
    for s in signals:
        if s.kind != SignalKind.CONTENT_INTERACTION or not s.content_format:
            continue
        w, ids = acc[s.content_format]
        acc[s.content_format] = (w + max(s.weight, 0.0), ids + [s.signal_id])
    if not acc:
        return []
    fmt, (weight, ids) = max(acc.items(), key=lambda kv: kv[1][0])
    conf = _cap(_confidence_from_weight(weight), cap)
    return [
        InferredTrait(
            kind=TraitKind.LEARNING_STYLE,
            value=fmt,
            confidence=conf,
            evidence_signal_ids=tuple(ids),
            explanation=(
                "inferred from the content formats the learner returns to and "
                "spends time with"
            ),
        )
    ]


# Map each trait kind to its behavioural inference rule.
_RULES = {
    TraitKind.INTEREST: _infer_interest,
    TraitKind.PREFERRED_SUBJECT: _infer_preferred_subject,
    TraitKind.PACE: _infer_pace,
    TraitKind.GOAL: _infer_goal,
    TraitKind.STRENGTH: _infer_strength,
    TraitKind.LEARNING_STYLE: _infer_learning_style,
}


def infer_profile(
    inp: InferenceInput,
    *,
    consents: Iterable[PersonalizationConsent],
    asof: datetime | None = None,
) -> InferredProfile:
    """Infer a provisional personalization profile from behavioural signals.

    GATED FIRST, PER TRAIT: each trait kind is checked against the consent +
    age-tier gate. Only permitted kinds are even attempted; an over-tier kind is
    omitted and recorded in ``denied_traits`` (with a plain-language reason) so a
    surface can transparently say "we do not infer this for you".

    Confidence on every produced trait is capped by the learner's tier ceiling
    (the more protected the tier, the more provisional the read). Works from
    signals alone — no questionnaire is ever consulted, because there is nowhere
    to pass one.
    """
    asof = asof or _now()
    consents = list(consents)
    signals = list(inp.all_signals())

    cap = effective_max_confidence(consents, subject=inp.subject, asof=asof)

    traits: list[InferredTrait] = []
    denied: list[tuple[str, str]] = []

    for kind, rule in _RULES.items():
        gate = evaluate_inference(
            subject=inp.subject, trait=kind, consents=consents, scope="profiling", asof=asof
        )
        if not gate.allowed:
            denied.append((kind.value, gate.reason))
            continue
        produced = rule(signals, cap)
        for t in produced:
            # Stamp the inference time and re-validate the invariants.
            traits.append(
                InferredTrait(
                    kind=t.kind,
                    value=t.value,
                    confidence=t.confidence,
                    evidence_signal_ids=t.evidence_signal_ids,
                    explanation=t.explanation,
                    provisional=True,
                    inferred_at=asof,
                )
            )

    return InferredProfile(
        subject=inp.subject,
        traits=tuple(traits),
        inferred_at=asof,
        denied_traits=tuple(denied),
    )


__all__ = [
    "SignalKind",
    "ContentFormat",
    "Signal",
    "OnboardingChoice",
    "InferredTrait",
    "InferenceInput",
    "InferredProfile",
    "infer_profile",
]
