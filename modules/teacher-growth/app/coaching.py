"""Private, evidence-based coaching signals (B10).

This is the heart of B10. It turns the descriptive lesson metrics from
``interaction.py`` into gentle, growth-oriented COACHING SIGNALS that surface
**to the teacher first** and are **private by default**.

Three rules are load-bearing and enforced in code, not just documented:

  1. **Teacher-first + private.** Every :class:`CoachingSignal` carries
     ``visibility = "teacher_first"`` and ``private = True``. The audience helper
     refuses to widen the audience beyond the teacher without an explicit,
     teacher-granted consent ref (CONSENT gates every cross-context read —
     INVARIANT 6). Nothing here pushes a signal to a principal or an open board.

  2. **No automated punitive ranking.** :func:`refuse_punitive_ranking` exists so
     the prohibition is a callable contract: any attempt to turn coaching signals
     into a teacher league table / auto-rank / auto-rating raises. There is no
     code path that orders teachers against each other or assigns a punitive
     grade. Coaching describes a lesson, suggests one next step, and stops.

  3. **Employment decisions require human review.** A signal can be voluntarily
     attached to a quality review (see ``quality_review.py``), but the signal
     itself never decides anything. :func:`employment_decision_guard` makes the
     "AI never decides employment" rule a hard error if anything tries.

Signals are framed as growth, never deficit: each pairs a plain-language reading
with ONE concrete, optional next step, the evidence behind it, and a confidence
band — explainable intelligence (principle 2). Pure, deterministic, import-safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .interaction import InteractionMetrics


SignalDimension = Literal[
    "talk_ratio", "questioning_quality", "equity_of_voice", "wait_time"
]
Confidence = Literal["low", "medium", "high"]
Direction = Literal["strength", "growth_area", "neutral"]


# Plain-language, research-informed reference points. These are GUIDES that frame
# a reflective signal, never pass/fail thresholds and never a basis for ranking.
# Tunable without changing behaviour semantics.
_TALK_RATIO_RICH = 0.65          # below this, the class is doing a lot of talking.
_TALK_RATIO_TEACHER_HEAVY = 0.80  # above this, the room is mostly teacher voice.
_HIGHER_ORDER_HEALTHY = 0.30      # a healthy share of open / why-how questions.
_EQUITY_HEALTHY = 0.60           # reasonably even spread of voices.
_WAIT_TIME_HEALTHY_S = 3.0       # the classic "three-second" thinking gap.
_MIN_QUESTIONS_FOR_CONFIDENCE = 5
_MIN_VOICES_FOR_CONFIDENCE = 4


class PunitiveRankingError(RuntimeError):
    """Raised on any attempt to rank/auto-rate teachers from coaching signals."""


class EmploymentDecisionError(RuntimeError):
    """Raised on any attempt to let coaching signals decide employment."""


def refuse_punitive_ranking(*_args: object, **_kwargs: object) -> "None":
    """The prohibition on automated punitive ranking, as a callable contract.

    B10 produces NO league table, NO auto-rank, NO punitive auto-rating of
    teachers. This function is the single place that documents and enforces it:
    calling it always raises, so any code (or test) that asserts "ranking is
    impossible here" has a concrete thing to call.
    """
    raise PunitiveRankingError(
        "Teacher growth never produces an automated punitive ranking. Coaching "
        "signals are private, teacher-first, and descriptive of a single lesson. "
        "Comparative judgement that affects a person is a human-reviewed process "
        "(see quality_review.py), not an automatic score."
    )


def employment_decision_guard(*_args: object, **_kwargs: object) -> "None":
    """Hard guard: coaching signals never auto-decide employment (INVARIANT 8).

    Hiring, firing, renewal, and pay are consequential human decisions. The AI
    may surface evidence into a human-owned review; it never fires the decision.
    """
    raise EmploymentDecisionError(
        "Coaching signals never make an employment decision. Consequential "
        "decisions about a person require a human-owned review and an explicit "
        "human approval; B10 only surfaces private, evidence-linked reflection."
    )


@dataclass(frozen=True)
class CoachingSignal:
    """One private, teacher-first coaching reflection on one dimension.

    Growth-framed: a reading, ONE optional next step, the evidence, a confidence
    band, and the audience guarantee. Never a ranking, never a verdict.
    """

    teacher_ref: str
    lesson_id: str
    dimension: SignalDimension
    direction: Direction
    reading: str
    suggested_next_step: str
    evidence: str
    confidence: Confidence
    visibility: str = "teacher_first"
    private: bool = True

    def __post_init__(self) -> None:
        # Defend the privacy invariant at construction: a coaching signal is
        # always private and teacher-first. There is no public coaching signal.
        if not self.private:
            raise ValueError("Coaching signals are always private (teacher-first).")
        if self.visibility != "teacher_first":
            raise ValueError("Coaching signal visibility is fixed to teacher_first.")

    @property
    def why_am_i_seeing_this(self) -> str:
        return (
            "This is a private reflection on your own lesson, shared with you "
            "first. It is not a rating and is not visible to anyone else unless "
            "you choose to share it."
        )

    def audience(self, *, shared_by_teacher_consent_ref: str | None = None) -> list[str]:
        """Who may read this signal.

        Default audience is the teacher alone. A teacher may VOLUNTARILY widen it
        by passing their own consent ref (e.g. to bring a signal into a coaching
        conversation). Without that explicit teacher consent the audience never
        widens — CONSENT gates the cross-context read (INVARIANT 6).
        """
        if shared_by_teacher_consent_ref:
            return ["teacher", "shared_with_consent"]
        return ["teacher"]


@dataclass
class CoachingSummary:
    """The set of private signals for one lesson, plus a teacher-first framing."""

    teacher_ref: str
    lesson_id: str
    signals: list[CoachingSignal] = field(default_factory=list)
    visibility: str = "teacher_first"
    private: bool = True

    @property
    def strengths(self) -> list[CoachingSignal]:
        return [s for s in self.signals if s.direction == "strength"]

    @property
    def growth_areas(self) -> list[CoachingSignal]:
        return [s for s in self.signals if s.direction == "growth_area"]

    def framing(self) -> str:
        return (
            "Private reflection on your lesson. Strengths first, then one or two "
            "things to try next. Yours to keep or share; never a rating."
        )


def _confidence_from_volume(samples: int, threshold: int) -> Confidence:
    """More observations -> more confidence. Deterministic banding."""
    if samples >= threshold:
        return "high"
    if samples >= max(1, threshold // 2):
        return "medium"
    return "low"


def _talk_ratio_signal(m: InteractionMetrics) -> CoachingSignal:
    ratio = m.teacher_talk_ratio
    ev = m.evidence()["talk_ratio"]
    if m.total_talk_s <= 0:
        direction: Direction = "neutral"
        reading = "No speaking time was captured for this lesson."
        step = "If this lesson had discussion, check the capture was running."
        conf: Confidence = "low"
    elif ratio <= _TALK_RATIO_RICH:
        direction = "strength"
        reading = "Learners did a healthy share of the talking."
        step = "Keep creating space for learner voice; it is working."
        conf = "high"
    elif ratio >= _TALK_RATIO_TEACHER_HEAVY:
        direction = "growth_area"
        reading = "The lesson leaned heavily on teacher talk."
        step = (
            "Try one think-pair-share or a short learner-led recap to shift more "
            "of the thinking to the class."
        )
        conf = "high"
    else:
        direction = "neutral"
        reading = "Talk was reasonably balanced, with room to open it up further."
        step = "Consider one extra open prompt to invite more learner talk."
        conf = "medium"
    return CoachingSignal(
        teacher_ref=m.teacher_ref, lesson_id=m.lesson_id, dimension="talk_ratio",
        direction=direction, reading=reading, suggested_next_step=step,
        evidence=ev, confidence=conf,
    )


def _questioning_signal(m: InteractionMetrics) -> CoachingSignal:
    frac = m.higher_order_fraction
    ev = m.evidence()["questioning_quality"]
    conf = _confidence_from_volume(m.total_questions, _MIN_QUESTIONS_FOR_CONFIDENCE)
    if m.total_questions == 0:
        direction: Direction = "neutral"
        reading = "No teacher questions were captured this lesson."
        step = "A few open questions can surface what the class is thinking."
    elif frac >= _HIGHER_ORDER_HEALTHY:
        direction = "strength"
        reading = "A good share of your questions invited reasoning, not just recall."
        step = "Keep the open, why-and-how questions coming."
    else:
        direction = "growth_area"
        reading = "Most questions were recall-level this lesson."
        step = (
            "Swap one or two recall checks for a why or how question to stretch "
            "the thinking."
        )
    return CoachingSignal(
        teacher_ref=m.teacher_ref, lesson_id=m.lesson_id,
        dimension="questioning_quality", direction=direction, reading=reading,
        suggested_next_step=step, evidence=ev, confidence=conf,
    )


def _equity_signal(m: InteractionMetrics) -> CoachingSignal:
    evenness = m.equity_of_voice
    ev = m.evidence()["equity_of_voice"]
    conf = _confidence_from_volume(m.voices_count, _MIN_VOICES_FOR_CONFIDENCE)
    if m.voices_count <= 1:
        direction: Direction = "neutral"
        reading = "Too few voices were captured to read the spread of participation."
        step = "Inviting a few more learners in makes participation easier to see."
    elif evenness >= _EQUITY_HEALTHY:
        direction = "strength"
        reading = "Participation was spread fairly evenly across the learners who spoke."
        step = "Keep drawing in a range of voices; the spread is healthy."
    else:
        direction = "growth_area"
        reading = "A few voices carried most of the discussion."
        step = (
            "Try a no-hands cold-call or a quick whole-class response to widen who "
            "contributes."
        )
    return CoachingSignal(
        teacher_ref=m.teacher_ref, lesson_id=m.lesson_id,
        dimension="equity_of_voice", direction=direction, reading=reading,
        suggested_next_step=step, evidence=ev, confidence=conf,
    )


def _wait_time_signal(m: InteractionMetrics) -> CoachingSignal:
    avg = m.average_wait_time_s
    ev = m.evidence()["wait_time"]
    conf = _confidence_from_volume(
        len(m.wait_time_samples), _MIN_QUESTIONS_FOR_CONFIDENCE
    )
    if not m.wait_time_samples:
        direction: Direction = "neutral"
        reading = "No wait-time after questions was captured this lesson."
        step = "Pausing a few seconds after a question gives everyone time to think."
    elif avg >= _WAIT_TIME_HEALTHY_S:
        direction = "strength"
        reading = "You gave the class real thinking time after questions."
        step = "Keep holding that pause; it lets more learners formulate an answer."
    else:
        direction = "growth_area"
        reading = "Responses came quickly after questions, with little pause."
        step = (
            "Try counting to three silently after a question before taking an "
            "answer."
        )
    return CoachingSignal(
        teacher_ref=m.teacher_ref, lesson_id=m.lesson_id, dimension="wait_time",
        direction=direction, reading=reading, suggested_next_step=step,
        evidence=ev, confidence=conf,
    )


def build_coaching_summary(metrics: InteractionMetrics) -> CoachingSummary:
    """Turn one lesson's interaction metrics into a private coaching summary.

    Pure and deterministic. Produces exactly four growth-framed signals (one per
    dimension), strengths-first. Produces NO ranking and NO verdict — see
    :func:`refuse_punitive_ranking`.
    """
    signals = [
        _talk_ratio_signal(metrics),
        _questioning_signal(metrics),
        _equity_signal(metrics),
        _wait_time_signal(metrics),
    ]
    return CoachingSummary(
        teacher_ref=metrics.teacher_ref,
        lesson_id=metrics.lesson_id,
        signals=signals,
    )
