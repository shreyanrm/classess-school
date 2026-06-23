"""Adaptive practice — select the next item by mastery + gaps (B7).

Practice contributes EVIDENCE, not a completion tick. Every practice item is an
attempt that produces an ``attempt.recorded`` event (see :mod:`learning.events`),
carrying the keystone independent-vs-supported flag and the assistance level
used. There is no "completed" tick anywhere in this module by design.

Selection is ADAPTIVE and MISTAKE-BASED:

  - Topics with a CONFIRMED gap come first — and the gap TYPE shapes the item,
    because each of the ten gap types needs a different response (a procedural
    gap -> guided practice on the method; an application gap -> varied-context
    transfer items; a retention gap -> spaced retrieval; a speed gap -> timed
    fluency, not new instruction; and so on). Collapsing every struggle into
    "do more questions" is exactly what the gap taxonomy exists to prevent.
  - Difficulty is matched to the learner's current band — just beyond what they
    can already do alone (the desirable-difficulty zone), never trivially easy
    and never crushingly hard.
  - The assistance rung offered is the FADED rung from :mod:`learning.ladder`,
    so support recedes as mastery rises and the system always declares whether
    it is helping or evaluating.

The mastery + gap reads come from the CORE intelligence engine
(:mod:`learning._engine`). When that engine is unavailable (degraded), a
deterministic, dependency-free heuristic over plain evidence records stands in,
clearly labelled, so the path still works offline.

Pure selection logic: given the same learner state, the same next item.
Import-safe: the engine and pydantic are imported lazily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Sequence

from . import _engine
from .ladder import next_state, LadderState

# Item-difficulty bands matched to mastery bands. The next item sits JUST beyond
# what the learner can already do alone — desirable difficulty, not despair.
_BAND_TARGET_DIFFICULTY: dict[str, float] = {
    "not-started": 0.25,
    "emerging": 0.35,
    "developing": 0.5,
    "secure": 0.65,
    "independent": 0.8,
}

# The response each gap type calls for, as a practice intent. Each gap type maps
# to a DISTINCT kind of practice — never a generic "more questions".
GAP_RESPONSE: dict[str, str] = {
    "prerequisite": "route back to the prerequisite topic before continuing here",
    "conceptual": "re-anchor the idea with a worked example, then a parallel item",
    "procedural": "guided step-by-step practice on the method",
    "application": "varied-context transfer items, not more of the same form",
    "retention": "spaced retrieval of previously secure material",
    "language": "the same item with hyperlocalized language support",
    "accuracy": "precision drills with a self-check step",
    "speed": "timed fluency on already-correct material, not new instruction",
    "confidence": "low-stakes independent items to build self-reliance",
    "support-dependency": "the same item with one rung less support than last time",
}

# Gap priority for selection: the most blocking gaps first. A prerequisite gap
# blocks everything downstream; a speed gap is a polish concern.
_GAP_PRIORITY: dict[str, int] = {
    "prerequisite": 0,
    "conceptual": 1,
    "support-dependency": 2,
    "procedural": 3,
    "application": 4,
    "retention": 5,
    "confidence": 6,
    "accuracy": 7,
    "language": 8,
    "speed": 9,
}


@dataclass(frozen=True)
class TopicState:
    """The per-topic learner state practice selection consumes.

    A degraded-friendly, dependency-free view that BOTH the CORE engine path and
    the fallback heuristic produce, so selection logic is identical either way.
    """

    topic_id: str
    band: str                     # mastery band (plain bands; never a raw number)
    independence: float           # the keystone dimension, in [0,1]
    performance: float            # recency-weighted success rate, in [0,1]
    observation_count: int
    last_rung_used: str | None    # the assistance rung the learner last used here
    recent_struggle: bool         # a fresh weak/failed attempt here
    confirmed_gap_types: tuple[str, ...] = ()   # confirmed gaps, by type
    proposed_gap_types: tuple[str, ...] = ()    # unconfirmed signals (never block)


@dataclass(frozen=True)
class PracticeSelection:
    """The next practice item recommendation, with its rationale and lineage."""

    topic_id: str
    target_difficulty: float
    ladder: LadderState
    reason: str                   # plain-language why-this-item (explainability)
    gap_type: str | None          # the gap this item responds to, if any
    gap_response: str | None      # the distinct response the gap type calls for
    priority: int                 # lower = more urgent
    degraded: bool                # True when chosen by the fallback heuristic


# ---------------------------------------------------------------------------
# Building TopicState from raw evidence — via the CORE engine, or the fallback.
# ---------------------------------------------------------------------------
def _struggled_recently(items: Iterable[Any]) -> bool:
    ordered = sorted(items, key=lambda it: getattr(it, "occurred_at"))
    return bool(ordered) and getattr(ordered[-1], "score", 0.0) < 0.5


def topic_state_from_engine(
    events: list[Any],
    *,
    subject: Any,
    topic_id: Any,
    graph: Any | None = None,
    asof: datetime | None = None,
) -> TopicState:
    """Build a ``TopicState`` using the CORE intelligence engine. Requires
    ``_engine.available()``."""
    proj = _engine.build_topic_projection(
        events, subject=subject, topic_id=topic_id, graph=graph, asof=asof
    )
    items = _engine.engine().collect_evidence(events, subject=subject, topic_id=topic_id)
    dims = proj.mastery.reading.dimensions
    last_rung = items[-1].assistance_level if items else None
    confirmed = tuple(g.gap_type for g in proj.gaps if g.confirmed)
    proposed = tuple(g.gap_type for g in proj.gaps if not g.confirmed)
    return TopicState(
        topic_id=str(topic_id),
        band=proj.mastery.reading.band,
        independence=dims.independence,
        performance=dims.performance,
        observation_count=proj.mastery.observation_count,
        last_rung_used=last_rung,
        recent_struggle=_struggled_recently(items),
        confirmed_gap_types=confirmed,
        proposed_gap_types=proposed,
    )


# ---------------------------------------------------------------------------
# Selection — identical logic for engine-derived or fallback TopicState.
# ---------------------------------------------------------------------------
def select_for_topic(state: TopicState, *, degraded: bool = False) -> PracticeSelection:
    """Recommend the next practice item for ONE topic.

    The gap (if any) shapes the item and the difficulty/rung follow the band.
    The assistance rung is the FADED rung — support recedes as mastery rises.
    """
    target_difficulty = _BAND_TARGET_DIFFICULTY.get(state.band, 0.5)

    gap_type: str | None = None
    gap_response: str | None = None
    priority = 100
    if state.confirmed_gap_types:
        gap_type = min(state.confirmed_gap_types, key=lambda g: _GAP_PRIORITY.get(g, 50))
        gap_response = GAP_RESPONSE.get(gap_type)
        priority = _GAP_PRIORITY.get(gap_type, 50)
        # Gap type tunes difficulty: speed/accuracy work on already-correct
        # material (keep difficulty at/below band); application stretches up.
        if gap_type in ("speed", "accuracy"):
            target_difficulty = max(0.2, target_difficulty - 0.1)
        elif gap_type == "application":
            target_difficulty = min(0.95, target_difficulty + 0.15)

    # The faded assistance rung. A support-dependency gap forces a struggle so we
    # deliberately step support down (recent_struggle False, fade applies).
    force_fade = gap_type == "support-dependency"
    ladder = next_state(
        band=state.band,
        independence=state.independence,
        last_rung_used=state.last_rung_used,
        recent_struggle=state.recent_struggle and not force_fade,
    )

    if gap_type is not None:
        reason = (
            f"Confirmed {gap_type} gap on this topic — {gap_response}. "
            f"{ladder.mode_declaration}"
        )
    elif state.observation_count == 0:
        reason = (
            "No evidence here yet — start with a guided item to see how this "
            f"works. {ladder.mode_declaration}"
        )
        priority = 40
    else:
        reason = (
            "No confirmed gap — practice just beyond what you can already do "
            f"alone, with support fading as you go. {ladder.mode_declaration}"
        )
        priority = 50

    return PracticeSelection(
        topic_id=state.topic_id,
        target_difficulty=round(target_difficulty, 3),
        ladder=ladder,
        reason=reason,
        gap_type=gap_type,
        gap_response=gap_response,
        priority=priority,
        degraded=degraded,
    )


def select_next(states: Iterable[TopicState], *, degraded: bool = False) -> PracticeSelection | None:
    """Pick the single next practice item across several candidate topics.

    Most urgent first: confirmed-gap topics (by gap priority) ahead of plain
    practice; within the same priority, the lowest-performance topic first so
    the learner's weakest secure footing is shored up. Returns None when there
    is nothing to practise.
    """
    selections = [select_for_topic(s, degraded=degraded) for s in states]
    if not selections:
        return None
    by_topic = {s.topic_id: s for s in states}
    selections.sort(
        key=lambda sel: (sel.priority, by_topic[sel.topic_id].performance, sel.topic_id)
    )
    return selections[0]


def select_next_from_events(
    events: list[Any],
    *,
    subject: Any,
    topic_ids: list[Any],
    graph: Any | None = None,
    asof: datetime | None = None,
) -> PracticeSelection | None:
    """Convenience: derive each topic's state from the event log (via the CORE
    engine) and pick the next item. Raises if the engine is unavailable — the
    caller should branch on :func:`learning._engine.available` and supply
    pre-built ``TopicState`` objects in the degraded path."""
    if not _engine.available():
        raise RuntimeError(_engine.degraded_reason() or "intelligence engine unavailable")
    states = [
        topic_state_from_engine(events, subject=subject, topic_id=t, graph=graph, asof=asof)
        for t in topic_ids
    ]
    return select_next(states, degraded=False)


# ===========================================================================
# Practice FORMATS — "a range of practice formats keeps it varied" (d12).
# ===========================================================================
# Selection above answers WHICH topic + difficulty + rung. The FORMAT is the
# shape the practice is delivered in — varied so practice does not collapse into
# one monotonous drill. Each format declares whether it is timed, how many items
# it carries, and which gap types it serves well, so the format follows the gap
# rather than being picked at random.


class PracticeFormat(str, Enum):
    """The catalogue of practice formats. Labels so a surface can switch on them
    and a test can assert the full set."""

    SINGLE_ITEM = "single_item"           # one targeted item — the default drill
    TOPIC_QUIZ = "topic_quiz"             # a short mixed quiz over one topic
    SPACED_RETRIEVAL = "spaced_retrieval"  # review of previously-secure material
    TIMED_FLUENCY = "timed_fluency"       # speed drill on already-correct material
    MIXED_REVIEW = "mixed_review"         # interleaved items across topics
    CHALLENGE = "challenge"               # a stretch item beyond the current band


ALL_PRACTICE_FORMATS: tuple[PracticeFormat, ...] = (
    PracticeFormat.SINGLE_ITEM,
    PracticeFormat.TOPIC_QUIZ,
    PracticeFormat.SPACED_RETRIEVAL,
    PracticeFormat.TIMED_FLUENCY,
    PracticeFormat.MIXED_REVIEW,
    PracticeFormat.CHALLENGE,
)


@dataclass(frozen=True)
class FormatSpec:
    """How a practice format behaves: item count, whether it is timed, and a plain
    learner-facing label."""

    fmt: PracticeFormat
    item_count: int
    timed: bool
    learner_label: str


FORMAT_SPECS: dict[PracticeFormat, FormatSpec] = {
    PracticeFormat.SINGLE_ITEM: FormatSpec(
        PracticeFormat.SINGLE_ITEM, 1, False, "one focused question"
    ),
    PracticeFormat.TOPIC_QUIZ: FormatSpec(
        PracticeFormat.TOPIC_QUIZ, 5, False, "a short quiz on this topic"
    ),
    PracticeFormat.SPACED_RETRIEVAL: FormatSpec(
        PracticeFormat.SPACED_RETRIEVAL, 3, False, "a quick review of things due to revisit"
    ),
    PracticeFormat.TIMED_FLUENCY: FormatSpec(
        PracticeFormat.TIMED_FLUENCY, 8, True, "a timed fluency burst on what you can already do"
    ),
    PracticeFormat.MIXED_REVIEW: FormatSpec(
        PracticeFormat.MIXED_REVIEW, 6, False, "a mixed set across a few topics"
    ),
    PracticeFormat.CHALLENGE: FormatSpec(
        PracticeFormat.CHALLENGE, 1, False, "one stretch question beyond your usual level"
    ),
}

# Which format best serves which gap type. Speed -> timed fluency (not new
# instruction); retention -> spaced retrieval; application -> mixed/interleaved;
# confidence -> a low-stakes topic quiz. The format follows the gap.
_GAP_FORMAT: dict[str, PracticeFormat] = {
    "speed": PracticeFormat.TIMED_FLUENCY,
    "retention": PracticeFormat.SPACED_RETRIEVAL,
    "application": PracticeFormat.MIXED_REVIEW,
    "confidence": PracticeFormat.TOPIC_QUIZ,
    "accuracy": PracticeFormat.SINGLE_ITEM,
    "procedural": PracticeFormat.SINGLE_ITEM,
    "conceptual": PracticeFormat.SINGLE_ITEM,
    "prerequisite": PracticeFormat.SINGLE_ITEM,
    "support-dependency": PracticeFormat.SINGLE_ITEM,
    "language": PracticeFormat.SINGLE_ITEM,
}


def recommend_format(state: TopicState) -> FormatSpec:
    """Pick the practice format that best suits this topic's state.

    The gap type drives it where there is one; an independent learner with no gap
    gets a challenge stretch; a topic with several observations and no gap gets a
    topic quiz to confirm comprehension; a fresh topic gets a single focused item.
    """
    if state.confirmed_gap_types:
        gap = min(state.confirmed_gap_types, key=lambda g: _GAP_PRIORITY.get(g, 50))
        return FORMAT_SPECS[_GAP_FORMAT.get(gap, PracticeFormat.SINGLE_ITEM)]
    if state.band == "independent" and not state.recent_struggle:
        return FORMAT_SPECS[PracticeFormat.CHALLENGE]
    if state.observation_count >= 4:
        return FORMAT_SPECS[PracticeFormat.TOPIC_QUIZ]
    return FORMAT_SPECS[PracticeFormat.SINGLE_ITEM]


# ===========================================================================
# Topic QUIZ — a short mixed quiz over one topic that "rewards comprehension".
# ===========================================================================
@dataclass(frozen=True)
class QuizItemResult:
    """One graded quiz item, as the aptitude tracker reads it."""

    correct: bool
    independent: bool          # the keystone flag: solved unaided?
    difficulty: float          # in [0,1]
    score: float | None = None  # optional partial credit; defaults from ``correct``

    @property
    def effective_score(self) -> float:
        if self.score is not None:
            return max(0.0, min(1.0, self.score))
        return 1.0 if self.correct else 0.0


@dataclass(frozen=True)
class QuizResult:
    """The outcome of one topic quiz. Comprehension-rewarding: an item solved at a
    higher difficulty INDEPENDENTLY counts for more than an easy supported one, so
    the quiz score is not a flat percentage of correct answers."""

    topic_id: str
    raw_correct: int
    total: int
    comprehension_score: float    # difficulty- and independence-weighted, in [0,1]
    independent_share: float      # share of items solved unaided
    plain_language: str

    @property
    def passed(self) -> bool:
        return self.comprehension_score >= 0.6


def grade_topic_quiz(topic_id: str, items: Sequence[QuizItemResult]) -> QuizResult:
    """Grade a topic quiz, rewarding comprehension over completion.

    Each item's contribution is weighted by its difficulty and by whether it was
    solved independently (an unaided correct answer on a hard item is the strongest
    signal of comprehension). Pure: same items -> same result.
    """
    if not items:
        raise ValueError("a topic quiz must have at least one item to grade.")
    total = len(items)
    raw_correct = sum(1 for it in items if it.correct)
    indep_correct = sum(1 for it in items if it.correct and it.independent)

    weighted = 0.0
    weight_sum = 0.0
    for it in items:
        # Difficulty sets the weight (harder items matter more); independence adds
        # a multiplier so an unaided solve outscores a supported one.
        w = 0.5 + it.difficulty            # in [0.5, 1.5]
        indep_mult = 1.0 if it.independent else 0.7
        weighted += it.effective_score * w * indep_mult
        weight_sum += w
    comprehension = weighted / weight_sum if weight_sum else 0.0
    comprehension = max(0.0, min(1.0, comprehension))
    indep_share = indep_correct / total

    if comprehension >= 0.85:
        plain = "strong comprehension on this topic"
    elif comprehension >= 0.6:
        plain = "solid understanding, with a little more to firm up"
    elif comprehension >= 0.35:
        plain = "the idea is forming, but it is not secure yet"
    else:
        plain = "this topic needs more work before a quiz will show comprehension"

    return QuizResult(
        topic_id=topic_id,
        raw_correct=raw_correct,
        total=total,
        comprehension_score=round(comprehension, 3),
        independent_share=round(indep_share, 3),
        plain_language=plain,
    )


# ===========================================================================
# Per-student READINESS / APTITUDE score, tracked through practice (d12).
# ===========================================================================
# A single, learner-facing aptitude reading that moves with practice evidence. It
# is NOT mastery (CORE owns that) and not a grade — it is a recency-weighted,
# independence-leaning read of how the learner is trending across their practice,
# the "readiness/aptitude score tracks per student" the document asks for.

# How sharply older practice fades relative to recent practice (half-life in
# items). Recent practice dominates so the score tracks the current trajectory.
_APTITUDE_HALFLIFE_ITEMS = 8.0


@dataclass(frozen=True)
class AptitudeReading:
    """A per-student aptitude/readiness reading derived from practice evidence.

    ``score`` is in [0,1]; ``trend`` says whether recent practice is above or
    below the learner's longer-run level; ``plain_language`` is the only thing a
    learner should see (never the raw number — CONFIDENTIALITY SCRUB)."""

    score: float
    independent_share: float       # how much of the strength is unaided
    sample_size: int
    trend: str                     # "rising" | "steady" | "slipping" | "too-early"
    band: str                      # plain band label
    plain_language: str


@dataclass(frozen=True)
class AptitudeObservation:
    """One practice item as the aptitude tracker reads it. Ordered oldest-first by
    ``order`` (or appended order)."""

    correct: bool
    independent: bool
    difficulty: float
    score: float | None = None

    @property
    def effective_score(self) -> float:
        if self.score is not None:
            return max(0.0, min(1.0, self.score))
        return 1.0 if self.correct else 0.0


def _aptitude_band(score: float) -> str:
    if score >= 0.8:
        return "excelling"
    if score >= 0.6:
        return "on-track"
    if score >= 0.4:
        return "developing"
    if score > 0.0:
        return "early"
    return "not-started"


def track_aptitude(observations: Sequence[AptitudeObservation]) -> AptitudeReading:
    """Compute the per-student readiness/aptitude score from practice history.

    Recency-weighted (recent practice dominates via an exponential decay over item
    order) and independence-leaning (an unaided correct answer on a harder item
    lifts aptitude more than a supported easy one). Deterministic: the same ordered
    practice history yields the same reading. With too few items it reports
    'too-early' rather than a misleadingly confident number.
    """
    obs = list(observations)
    n = len(obs)
    if n == 0:
        return AptitudeReading(
            score=0.0, independent_share=0.0, sample_size=0, trend="too-early",
            band="not-started",
            plain_language="not enough practice yet to read your trajectory",
        )

    # Recency weights: the most recent item has weight 1, older items decay by a
    # half-life measured in items. obs[-1] is the newest.
    import math

    weighted = 0.0
    weight_sum = 0.0
    indep_weighted = 0.0
    for idx, it in enumerate(obs):
        age = (n - 1) - idx                       # 0 for newest
        recency = 0.5 ** (age / _APTITUDE_HALFLIFE_ITEMS)
        difficulty_w = 0.5 + it.difficulty        # harder items count more
        indep_mult = 1.0 if it.independent else 0.7
        w = recency * difficulty_w
        weighted += it.effective_score * w * indep_mult
        indep_weighted += (1.0 if (it.correct and it.independent) else 0.0) * recency
        weight_sum += w
    score = max(0.0, min(1.0, weighted / weight_sum)) if weight_sum else 0.0
    recency_sum = sum(0.5 ** (((n - 1) - i) / _APTITUDE_HALFLIFE_ITEMS) for i in range(n))
    indep_share = round(indep_weighted / recency_sum, 3) if recency_sum else 0.0

    # Trend: compare the recent half against the older half (when there is enough).
    if n < 4:
        trend = "too-early"
    else:
        mid = n // 2
        older = obs[:mid]
        recent = obs[mid:]
        older_avg = sum(o.effective_score for o in older) / len(older)
        recent_avg = sum(o.effective_score for o in recent) / len(recent)
        delta = recent_avg - older_avg
        if delta > 0.1:
            trend = "rising"
        elif delta < -0.1:
            trend = "slipping"
        else:
            trend = "steady"

    band = _aptitude_band(score)
    plain_by_trend = {
        "rising": "your recent practice is trending up",
        "slipping": "your recent practice has dipped — worth a steady push",
        "steady": "you are holding a consistent level",
        "too-early": "still building a picture of your trajectory",
    }
    return AptitudeReading(
        score=round(score, 3),
        independent_share=indep_share,
        sample_size=n,
        trend=trend,
        band=band,
        plain_language=plain_by_trend[trend],
    )
