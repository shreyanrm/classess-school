"""Classroom-interaction analysis (B10).

Turns raw delivery/engagement events from a single lesson into the four
deterministic interaction metrics B10 cares about:

  - **talk ratio**          — share of speaking time that was the teacher's vs
                              the class's. A research-backed proxy for how much
                              the room is doing the thinking.
  - **questioning quality** — the mix of higher-order (open / why-how) vs
                              lower-order (recall / closed) questions, and the
                              question rate.
  - **equity of voice**     — how evenly participation is spread across the
                              learners who spoke (a Gini-style evenness), so a
                              lesson carried by three voices is visible.
  - **wait time**           — the average pause between a teacher question and
                              the next learner response (the "thinking gap").

DESIGN STANCE (non-negotiable for B10):
  - These are **descriptive** lesson metrics, not scores on a person. Nothing
    here ranks teachers or produces a league table — that belongs to no module
    (see ``coaching.py`` which refuses to build one).
  - Inputs carry **opaque speaker refs only** (``canonical_uuid`` for the
    teacher, opaque ``participant_ref`` for each learner). No names, no PII
    (INVARIANT 1 + 2). The analysis is keyed to a lesson, not to a roster.
  - Pure and deterministic: identical events in -> identical metrics out, with
    no network, DB, model, or wall-clock dependency. This is what makes the
    "metrics computed deterministically" guarantee testable.

Pure, dependency-free, import-safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal


SpeakerRole = Literal["teacher", "learner"]
QuestionLevel = Literal["higher_order", "lower_order"]


# ---------------------------------------------------------------------------
# Raw interaction observations (opaque refs only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Utterance:
    """One speaking turn observed in a lesson.

    ``speaker_ref`` is the opaque ref of whoever spoke (the teacher's
    canonical_uuid, or an opaque per-learner participant ref). ``duration_s`` is
    how long they spoke. ``is_question`` / ``question_level`` describe a teacher
    question; ``responded_after_s`` is the wait before the next learner spoke
    (the wait-time gap), populated only on a teacher question that drew a reply.
    """

    speaker_ref: str
    role: SpeakerRole
    duration_s: float
    is_question: bool = False
    question_level: QuestionLevel | None = None
    responded_after_s: float | None = None

    def __post_init__(self) -> None:
        if self.duration_s < 0:
            raise ValueError("duration_s must be non-negative.")
        if self.responded_after_s is not None and self.responded_after_s < 0:
            raise ValueError("responded_after_s must be non-negative.")
        if self.is_question and self.role != "teacher":
            # B10 measures TEACHER questioning quality; a learner asking a
            # question is valuable but is not what this metric is about.
            raise ValueError("Only a teacher utterance can be a tracked question.")
        if self.question_level is not None and not self.is_question:
            raise ValueError("question_level is only meaningful on a question.")


def _gini_evenness(values: list[float]) -> float:
    """Return an evenness score in [0, 1] (1 = perfectly even participation).

    Computed as ``1 - Gini``. With zero or one contributing speaker the notion
    of evenness is undefined; we return 0.0 (no spread to speak of).
    """
    positives = [v for v in values if v > 0]
    n = len(positives)
    if n <= 1:
        return 0.0
    total = sum(positives)
    if total <= 0:
        return 0.0
    positives.sort()
    cumulative = 0.0
    for i, v in enumerate(positives, start=1):
        cumulative += i * v
    gini = (2.0 * cumulative) / (n * total) - (n + 1.0) / n
    evenness = 1.0 - gini
    # Clamp against floating-point drift.
    return round(max(0.0, min(1.0, evenness)), 4)


@dataclass
class InteractionMetrics:
    """The deterministic interaction profile of ONE lesson.

    Descriptive only. Each metric is paired with the evidence that produced it
    so the teacher sees why, not just a number (explainable intelligence).
    """

    lesson_id: str
    teacher_ref: str

    teacher_talk_s: float
    learner_talk_s: float

    total_questions: int
    higher_order_questions: int
    lower_order_questions: int

    wait_time_samples: list[float] = field(default_factory=list)
    learner_talk_by_ref: dict[str, float] = field(default_factory=dict)

    # ---- talk ratio -------------------------------------------------------
    @property
    def total_talk_s(self) -> float:
        return round(self.teacher_talk_s + self.learner_talk_s, 2)

    @property
    def teacher_talk_ratio(self) -> float:
        """Fraction of speaking time that was the teacher's, in [0, 1]. 0.0 when
        nobody spoke (no signal rather than a misleading 100%)."""
        total = self.teacher_talk_s + self.learner_talk_s
        if total <= 0:
            return 0.0
        return round(self.teacher_talk_s / total, 4)

    @property
    def learner_talk_ratio(self) -> float:
        total = self.teacher_talk_s + self.learner_talk_s
        if total <= 0:
            return 0.0
        return round(self.learner_talk_s / total, 4)

    # ---- questioning quality ---------------------------------------------
    @property
    def higher_order_fraction(self) -> float:
        """Share of questions that were higher-order, in [0, 1]."""
        if self.total_questions <= 0:
            return 0.0
        return round(self.higher_order_questions / self.total_questions, 4)

    # ---- equity of voice --------------------------------------------------
    @property
    def voices_count(self) -> int:
        """Distinct learners who contributed any speaking time."""
        return sum(1 for v in self.learner_talk_by_ref.values() if v > 0)

    @property
    def equity_of_voice(self) -> float:
        """Evenness of learner participation in [0, 1] (1 = perfectly even)."""
        return _gini_evenness(list(self.learner_talk_by_ref.values()))

    # ---- wait time --------------------------------------------------------
    @property
    def average_wait_time_s(self) -> float:
        """Mean thinking gap after a teacher question, in seconds. 0.0 when no
        question drew a measurable response."""
        if not self.wait_time_samples:
            return 0.0
        return round(sum(self.wait_time_samples) / len(self.wait_time_samples), 2)

    # ---- explainability ---------------------------------------------------
    def evidence(self) -> dict[str, str]:
        """Plain-language evidence for each metric — what produced the number."""
        return {
            "talk_ratio": (
                f"Teacher spoke {self.teacher_talk_s:.0f}s of "
                f"{self.total_talk_s:.0f}s total "
                f"({self.teacher_talk_ratio * 100:.0f}% teacher talk)."
            ),
            "questioning_quality": (
                f"{self.total_questions} question(s): "
                f"{self.higher_order_questions} higher-order, "
                f"{self.lower_order_questions} lower-order "
                f"({self.higher_order_fraction * 100:.0f}% higher-order)."
            ),
            "equity_of_voice": (
                f"{self.voices_count} learner voice(s) contributed; "
                f"participation evenness {self.equity_of_voice:.2f} of 1.00."
            ),
            "wait_time": (
                f"Average thinking gap {self.average_wait_time_s:.1f}s across "
                f"{len(self.wait_time_samples)} response(s)."
            ),
        }


def analyse_interaction(
    *,
    lesson_id: str,
    teacher_ref: str,
    utterances: Iterable[Utterance],
) -> InteractionMetrics:
    """Compute the four interaction metrics for one lesson. Pure; deterministic.

    ``utterances`` is the ordered, opaque-ref stream of speaking turns from the
    delivery/engagement events of a single lesson. No PII is read; no network or
    model is involved.
    """
    teacher_talk = 0.0
    learner_talk = 0.0
    learner_by_ref: dict[str, float] = {}
    total_q = 0
    higher_q = 0
    lower_q = 0
    waits: list[float] = []

    for u in utterances:
        if u.role == "teacher":
            teacher_talk += u.duration_s
            if u.is_question:
                total_q += 1
                if u.question_level == "higher_order":
                    higher_q += 1
                elif u.question_level == "lower_order":
                    lower_q += 1
                if u.responded_after_s is not None:
                    waits.append(u.responded_after_s)
        else:
            learner_talk += u.duration_s
            learner_by_ref[u.speaker_ref] = (
                learner_by_ref.get(u.speaker_ref, 0.0) + u.duration_s
            )

    return InteractionMetrics(
        lesson_id=lesson_id,
        teacher_ref=teacher_ref,
        teacher_talk_s=round(teacher_talk, 2),
        learner_talk_s=round(learner_talk, 2),
        total_questions=total_q,
        higher_order_questions=higher_q,
        lower_order_questions=lower_q,
        wait_time_samples=[round(w, 2) for w in waits],
        learner_talk_by_ref={k: round(v, 2) for k, v in learner_by_ref.items()},
    )
