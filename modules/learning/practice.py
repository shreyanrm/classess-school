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
from typing import Any, Iterable

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
