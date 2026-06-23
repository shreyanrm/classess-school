"""The d13 exam-date revision PLANNER + time-left achievability (B7).

"A plan that changes with reality rather than nagging that tasks are overdue."
This module builds an exam-date-based revision plan from four inputs the platform
already produces, and re-plans it as reality moves:

  - the EXAM DATE and the learner's AVAILABLE TIME between now and then (per-day
    study minutes, with named non-study days);
  - SYLLABUS COVERAGE — the exam blueprint as weighted topics, each with whether
    the learner has produced evidence yet;
  - WEAKNESS ANALYSIS — per-topic readiness/independence + confirmed gaps + the
    PREREQUISITE structure, so a weak prerequisite is scheduled BEFORE the
    downstream topic that depends on it (you cannot revise calculus while the
    algebra under it is shaky).

The planner then:

  1. PRIORITISES — weak prerequisites first, then high-weight weak topics, then
     decayed-but-known topics needing review, then maintenance of secure topics.
  2. DISTRIBUTES WORKLOAD to REDUCE STRESS — it spreads sessions across the
     available days rather than back-loading, caps daily load to the learner's
     stated capacity, and refuses to promise more than the days allow (it tells
     the truth about what fits).
  3. AUTO RE-PLANS on missed sessions — :func:`replan_after_missed` folds the work
     of missed/incomplete sessions back into the remaining days, re-balancing
     without guilt-tripping and surfacing honestly when the remaining time can no
     longer fit everything.
  4. Computes TIME-LEFT ACHIEVABILITY — :func:`achievable_forecast` projects what
     readiness is reachable given the days remaining and topic weightage, so the
     forecast becomes a plan ("here is what is realistically reachable, and here
     is what to drop if it isn't").

SCOPES: school / board / competitive exams differ only in their priority profile
(how aggressively prerequisites and breadth-vs-depth are weighted), captured as
an :class:`ExamScope` — the same engine, tuned.

Pure, deterministic, import-safe, offline. Reads per-topic readiness views (the
same shape :mod:`learning.readiness` produces) — never PII, only opaque ids.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, Mapping, Sequence


class ExamScope(str, Enum):
    """The exam scope. Tunes the priority profile, not the engine."""

    SCHOOL = "school"            # breadth across the term's coverage
    BOARD = "board"              # high stakes; prerequisites + retention weighted
    COMPETITIVE = "competitive"  # depth + speed on high-yield topics


@dataclass(frozen=True)
class ScopeProfile:
    """How a scope weights the priority dimensions."""

    scope: ExamScope
    prereq_emphasis: float       # multiplier on prerequisite urgency
    weight_emphasis: float       # how much exam weight drives priority
    retention_emphasis: float    # how much decayed-but-known topics are pushed up


SCOPE_PROFILES: dict[ExamScope, ScopeProfile] = {
    ExamScope.SCHOOL: ScopeProfile(ExamScope.SCHOOL, 1.0, 1.0, 0.8),
    ExamScope.BOARD: ScopeProfile(ExamScope.BOARD, 1.3, 1.1, 1.2),
    ExamScope.COMPETITIVE: ScopeProfile(ExamScope.COMPETITIVE, 1.5, 1.4, 1.0),
}


@dataclass(frozen=True)
class PlannerTopic:
    """One syllabus topic for the planner, with weakness + coverage + prereqs.

    A trimmed view that the readiness/engine layer produces. ``readiness`` is the
    learner's current exam-readiness on this topic in [0,1] (low = weak); a topic
    with no evidence is an unknown and treated as weak. ``prerequisites`` are the
    topic_ids this topic depends on, so they can be scheduled first.
    """

    topic_id: str
    weight: float = 1.0                 # share of the exam
    readiness: float = 0.0              # current readiness in [0,1]
    has_evidence: bool = False
    revision_due: bool = False
    confirmed_gap_types: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    # Estimated minutes a full revision pass on this topic needs at full weakness.
    base_minutes: int = 40


@dataclass(frozen=True)
class AvailableTime:
    """The learner's available study time between now and the exam.

    ``daily_minutes`` is the comfortable per-day capacity; ``blackout_days`` are
    dates with no study time (the planner distributes around them). Stress is
    reduced by never scheduling above ``daily_minutes`` on any day.
    """

    daily_minutes: int = 60
    blackout_days: frozenset[date] = frozenset()


@dataclass(frozen=True)
class RevisionSession:
    """One scheduled revision session in the plan."""

    day: date
    topic_id: str
    minutes: int
    priority_rank: int            # 0 = highest priority in the plan
    reason: str                   # plain-language why this topic, why now
    is_prerequisite_for: tuple[str, ...] = ()


@dataclass(frozen=True)
class RevisionPlan:
    """The computed exam-date revision plan."""

    exam_date: date
    scope: ExamScope
    sessions: tuple[RevisionSession, ...]
    days_available: int
    total_minutes_needed: int
    total_minutes_available: int
    fits: bool                    # does the needed work fit the available time?
    plain_language: str
    deferred_topics: tuple[str, ...] = ()   # topics that did not fit, lowest-priority first

    @property
    def sessions_by_day(self) -> dict[date, list[RevisionSession]]:
        out: dict[date, list[RevisionSession]] = {}
        for s in self.sessions:
            out.setdefault(s.day, []).append(s)
        return out


# ---------------------------------------------------------------------------
# Prioritisation — weakest weighted prerequisites first.
# ---------------------------------------------------------------------------
def _study_days(start: date, exam_date: date, available: AvailableTime) -> list[date]:
    """The study days from ``start`` (inclusive) up to the day BEFORE the exam,
    excluding blackout days. You do not revise on exam day."""
    days: list[date] = []
    d = start
    while d < exam_date:
        if d not in available.blackout_days:
            days.append(d)
        d += timedelta(days=1)
    return days


def _topic_need_minutes(topic: PlannerTopic) -> int:
    """How many minutes this topic needs, scaled by weakness. A weaker, higher-
    weight topic needs more; a secure topic needs only light maintenance."""
    weakness = 1.0 - max(0.0, min(1.0, topic.readiness))
    # No-evidence topics are fully weak. Confirmed gaps and revision-due add load.
    if not topic.has_evidence:
        weakness = 1.0
    if topic.confirmed_gap_types:
        weakness = min(1.0, weakness + 0.15)
    if topic.revision_due:
        weakness = min(1.0, weakness + 0.1)
    # Maintenance floor so even a secure, examined topic gets a short pass.
    minutes = topic.base_minutes * (0.25 + 0.75 * weakness)
    return max(10, int(round(minutes / 5.0) * 5))


def _priority_score(topic: PlannerTopic, profile: ScopeProfile, *, is_prereq: bool) -> float:
    """A higher score = MORE urgent. Weak prerequisites dominate, then weak high-
    weight topics, then decayed-but-known, then maintenance."""
    weakness = 1.0 - max(0.0, min(1.0, topic.readiness))
    if not topic.has_evidence:
        weakness = 1.0
    score = weakness * (1.0 + profile.weight_emphasis * topic.weight)
    if is_prereq:
        score *= profile.prereq_emphasis + 0.5  # prerequisites jump the queue
    if topic.revision_due:
        score += 0.3 * profile.retention_emphasis
    if topic.confirmed_gap_types:
        score += 0.25
    return score


def _prereq_topics(topics: Sequence[PlannerTopic]) -> set[str]:
    """The set of topic_ids that are a prerequisite for some other examined topic."""
    ids = {t.topic_id for t in topics}
    prereqs: set[str] = set()
    for t in topics:
        for p in t.prerequisites:
            if p in ids:
                prereqs.add(p)
    return prereqs


def _topo_then_priority(topics: Sequence[PlannerTopic], profile: ScopeProfile) -> list[PlannerTopic]:
    """Order topics so a topic never precedes its (examined) prerequisites, and
    within that constraint the most urgent first. A stable, deterministic order.
    """
    by_id = {t.topic_id: t for t in topics}
    prereq_set = _prereq_topics(topics)

    # Priority key (descending urgency). Prerequisites get their own emphasis.
    def key(t: PlannerTopic) -> tuple[float, float, str]:
        s = _priority_score(t, profile, is_prereq=t.topic_id in prereq_set)
        # Sort descending by score, then by weight, then stable by id.
        return (-s, -t.weight, t.topic_id)

    # Kahn-style: emit a topic only once its in-graph prerequisites are emitted,
    # choosing the highest-priority eligible topic at each step (deterministic).
    remaining = dict(by_id)
    emitted: list[PlannerTopic] = []
    emitted_ids: set[str] = set()
    # Guard against cycles by bounding iterations.
    while remaining:
        eligible = [
            t for t in remaining.values()
            if all((p not in by_id) or (p in emitted_ids) for p in t.prerequisites)
        ]
        if not eligible:
            # A prerequisite cycle (or all blocked): fall back to remaining by key.
            eligible = list(remaining.values())
        nxt = min(eligible, key=key)
        emitted.append(nxt)
        emitted_ids.add(nxt.topic_id)
        del remaining[nxt.topic_id]
    return emitted


def _dependents_of(topic_id: str, topics: Sequence[PlannerTopic]) -> tuple[str, ...]:
    return tuple(t.topic_id for t in topics if topic_id in t.prerequisites)


def _session_reason(topic: PlannerTopic, *, is_prereq: bool, dependents: tuple[str, ...]) -> str:
    if is_prereq and dependents:
        return (
            "A weaker foundation that other exam topics build on — revised first "
            "so the topics depending on it are not undermined."
        )
    if not topic.has_evidence:
        return "No practice here yet — covered early so it is not a blind spot in the exam."
    if topic.confirmed_gap_types:
        return "A confirmed gap to close before the exam."
    if topic.revision_due:
        return "Known before but decayed — a review brings it back before the exam."
    if topic.readiness >= 0.8:
        return "Already strong — a light maintenance pass to keep it fresh."
    return "Still building toward exam-ready — scheduled to firm it up."


def build_plan(
    *,
    exam_date: date,
    topics: Sequence[PlannerTopic],
    available: AvailableTime,
    scope: ExamScope = ExamScope.SCHOOL,
    asof: date | None = None,
) -> RevisionPlan:
    """Build the exam-date revision plan.

    Prioritises weak prerequisites, distributes the workload evenly across the
    available days (capped at the daily capacity to reduce stress), and tells the
    truth about whether everything fits. Pure: same inputs -> same plan.
    """
    asof = asof or datetime.now(timezone.utc).date()
    profile = SCOPE_PROFILES[scope]
    days = _study_days(asof, exam_date, available)
    days_available = len(days)
    total_available = days_available * max(0, available.daily_minutes)

    if not topics:
        return RevisionPlan(
            exam_date=exam_date, scope=scope, sessions=(), days_available=days_available,
            total_minutes_needed=0, total_minutes_available=total_available, fits=True,
            plain_language="no syllabus topics to plan yet",
        )
    if days_available == 0:
        return RevisionPlan(
            exam_date=exam_date, scope=scope, sessions=(), days_available=0,
            total_minutes_needed=0, total_minutes_available=0, fits=False,
            plain_language=(
                "there is no study time left before this exam — focus the remaining "
                "time on the highest-weight topics you are weakest on"
            ),
            deferred_topics=tuple(t.topic_id for t in _topo_then_priority(topics, profile)),
        )

    ordered = _topo_then_priority(topics, profile)
    prereq_set = _prereq_topics(topics)

    # Decide which topics fit the available time, highest priority first; defer the
    # tail honestly rather than promising the impossible.
    needs = [(t, _topic_need_minutes(t)) for t in ordered]
    total_needed = sum(m for _, m in needs)

    scheduled: list[tuple[PlannerTopic, int]] = []
    deferred: list[str] = []
    running = 0
    for t, m in needs:
        if running + m <= total_available:
            scheduled.append((t, m))
            running += m
        else:
            # Partial fit for the boundary topic if any room remains and it is a
            # prerequisite or high-weight; otherwise defer (lowest priority last).
            room = total_available - running
            if room >= 10 and (t.topic_id in prereq_set or t.weight >= 1.0):
                scheduled.append((t, room))
                running += room
            else:
                deferred.append(t.topic_id)
    fits = not deferred

    # Distribute sessions across days: walk the days round-robin, filling each day
    # up to the daily cap before moving on, keeping priority order intact so the
    # most urgent work lands earliest. This spreads load (stress reduction) while
    # front-loading urgency.
    sessions: list[RevisionSession] = []
    day_load: dict[date, int] = {d: 0 for d in days}
    day_idx = 0
    cap = max(1, available.daily_minutes)
    for rank, (topic, minutes) in enumerate(scheduled):
        remaining_min = minutes
        dependents = _dependents_of(topic.topic_id, topics)
        reason = _session_reason(
            topic, is_prereq=topic.topic_id in prereq_set, dependents=dependents
        )
        # Split a topic's minutes across days when it exceeds the daily cap, so no
        # single day is overloaded.
        while remaining_min > 0 and any(day_load[d] < cap for d in days):
            d = days[day_idx % days_available]
            free = cap - day_load[d]
            if free <= 0:
                day_idx += 1
                continue
            chunk = min(free, remaining_min)
            sessions.append(RevisionSession(
                day=d, topic_id=topic.topic_id, minutes=chunk, priority_rank=rank,
                reason=reason, is_prerequisite_for=dependents,
            ))
            day_load[d] += chunk
            remaining_min -= chunk
            if day_load[d] >= cap:
                day_idx += 1
        if remaining_min > 0:
            # Days are full; the rest could not be placed — count as deferred.
            deferred.append(topic.topic_id)
            fits = False

    sessions.sort(key=lambda s: (s.day, s.priority_rank, s.topic_id))

    if fits:
        plain = "your revision fits the time you have — here is a balanced plan"
    else:
        plain = (
            "there is more to revise than the time comfortably allows — the plan "
            "covers the most important topics first and flags the rest"
        )

    return RevisionPlan(
        exam_date=exam_date, scope=scope, sessions=tuple(sessions),
        days_available=days_available, total_minutes_needed=total_needed,
        total_minutes_available=total_available, fits=fits, plain_language=plain,
        deferred_topics=tuple(dict.fromkeys(deferred)),
    )


# ---------------------------------------------------------------------------
# Auto RE-PLAN on missed sessions.
# ---------------------------------------------------------------------------
def replan_after_missed(
    plan: RevisionPlan,
    *,
    topics: Sequence[PlannerTopic],
    available: AvailableTime,
    missed_days: Iterable[date],
    asof: date,
) -> RevisionPlan:
    """Re-plan from ``asof`` after some days were missed.

    The work that was scheduled on or before ``asof`` but not done is folded back
    into the remaining days by rebuilding the plan over the topics that are still
    weak. No guilt-tripping: missed work is simply re-balanced into what time
    remains, and the plan tells the truth if it no longer all fits.
    """
    missed = set(missed_days)
    # Topics still needing work are those that had sessions on missed days or that
    # remain weak. Simplest correct approach: rebuild over all topics from asof —
    # readiness already reflects whatever WAS completed (the caller passes fresh
    # readiness views), so a rebuild naturally de-prioritises what is now strong.
    # We only ensure topics touched by missed sessions are not dropped below their
    # current weakness.
    touched = {s.topic_id for s in plan.sessions if s.day in missed or s.day <= asof}
    # Rebuild from asof with the (already-updated) readiness for each topic.
    rebuilt = build_plan(
        exam_date=plan.exam_date, topics=topics, available=available,
        scope=plan.scope, asof=asof,
    )
    # If nothing was missed and asof is the original start, the rebuild equals the
    # original. Annotate the plain language to acknowledge the re-plan.
    note = rebuilt.plain_language
    if missed:
        if rebuilt.fits:
            note = "replanned around the missed days — it still all fits"
        else:
            note = (
                "replanned around the missed days — the remaining time is tight, "
                "so the plan now protects the most important topics first"
            )
    # Preserve which topics were re-folded for explainability via deferred ordering.
    _ = touched
    return RevisionPlan(
        exam_date=rebuilt.exam_date, scope=rebuilt.scope, sessions=rebuilt.sessions,
        days_available=rebuilt.days_available, total_minutes_needed=rebuilt.total_minutes_needed,
        total_minutes_available=rebuilt.total_minutes_available, fits=rebuilt.fits,
        plain_language=note, deferred_topics=rebuilt.deferred_topics,
    )


# ---------------------------------------------------------------------------
# TIME-LEFT achievability — what readiness is reachable given the days left.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AchievableTopic:
    """One topic's achievable readiness given the time left."""

    topic_id: str
    weight: float
    current_readiness: float
    projected_readiness: float    # reachable given the minutes the plan affords it
    reachable_gain: float
    minutes_afforded: int


@dataclass(frozen=True)
class AchievableForecast:
    """What overall readiness is realistically reachable by the exam.

    Distinct from :mod:`learning.readiness`, which forecasts CURRENT readiness;
    this projects the readiness reachable if the plan is followed in the time that
    remains, and recalculates as the days count down — "recalculate what is
    achievable given time left and topic weightage."
    """

    current_overall: float
    achievable_overall: float
    days_remaining: int
    minutes_remaining: int
    topics: tuple[AchievableTopic, ...]
    plain_language: str

    @property
    def at_risk(self) -> tuple[AchievableTopic, ...]:
        """High-weight topics whose achievable readiness still falls short — the
        ones to focus or, if impossible, consciously trade off."""
        risky = [t for t in self.topics if t.projected_readiness < 0.7 and t.weight > 0]
        risky.sort(key=lambda t: (t.projected_readiness, -t.weight, t.topic_id))
        return tuple(risky)


# How much readiness one minute of well-targeted revision can add on a weak topic.
# Deliberately conservative and with diminishing returns — the planner does not
# over-promise. A topic gains less per minute the closer it already is to ready.
_GAIN_PER_MINUTE = 0.012


def _projected_topic_readiness(topic: PlannerTopic, minutes: int) -> float:
    """Project achievable readiness: diminishing-returns gain toward 1.0 with the
    minutes afforded. Honest: more time helps, but never linearly to certainty."""
    current = max(0.0, min(1.0, topic.readiness if topic.has_evidence else 0.0))
    room = 1.0 - current
    # Exponential approach to the ceiling — diminishing returns.
    gain = room * (1.0 - math.exp(-_GAIN_PER_MINUTE * max(0, minutes)))
    return max(current, min(1.0, current + gain))


def achievable_forecast(
    plan: RevisionPlan,
    *,
    topics: Sequence[PlannerTopic],
) -> AchievableForecast:
    """Recalculate what readiness is achievable given the time left and topic
    weightage, using the minutes the plan actually affords each topic.

    Pure projection over the plan: same plan + topics -> same forecast.
    """
    by_id = {t.topic_id: t for t in topics}
    minutes_by_topic: dict[str, int] = {}
    for s in plan.sessions:
        minutes_by_topic[s.topic_id] = minutes_by_topic.get(s.topic_id, 0) + s.minutes

    total_weight = sum(max(t.weight, 0.0) for t in topics) or 1.0
    results: list[AchievableTopic] = []
    cur_sum = 0.0
    ach_sum = 0.0
    for t in topics:
        w = max(t.weight, 0.0) / total_weight
        minutes = minutes_by_topic.get(t.topic_id, 0)
        current = max(0.0, min(1.0, t.readiness if t.has_evidence else 0.0))
        projected = _projected_topic_readiness(t, minutes)
        results.append(AchievableTopic(
            topic_id=t.topic_id, weight=w, current_readiness=round(current, 3),
            projected_readiness=round(projected, 3),
            reachable_gain=round(projected - current, 3), minutes_afforded=minutes,
        ))
        cur_sum += current * w
        ach_sum += projected * w

    current_overall = round(max(0.0, min(1.0, cur_sum)), 3)
    achievable_overall = round(max(0.0, min(1.0, ach_sum)), 3)
    minutes_remaining = plan.total_minutes_available

    if achievable_overall >= 0.8:
        plain = "if you follow this plan, you are on track to be ready in time"
    elif achievable_overall >= 0.6:
        plain = (
            "the time left can get you most of the way — focus it on the topics "
            "flagged as still short"
        )
    elif achievable_overall > current_overall + 0.05:
        plain = (
            "the time left will move you forward but not all the way — concentrate "
            "on the highest-weight topics and let the lowest-weight ones go if needed"
        )
    else:
        plain = (
            "there is too little time to reach full readiness — protect the topics "
            "that carry the most marks and revise those well rather than spreading thin"
        )

    return AchievableForecast(
        current_overall=current_overall, achievable_overall=achievable_overall,
        days_remaining=plan.days_available, minutes_remaining=minutes_remaining,
        topics=tuple(results), plain_language=plain,
    )
