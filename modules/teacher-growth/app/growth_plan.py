"""Private development plans + the de-identified leadership aggregate (B10).

This deepens B10 toward the two parts of the spec that the single-lesson
coaching path does not yet reach (classess-school.html, "Private, evidence-based
growth"):

  - **Development plans.** Growth is longitudinal, not a single lesson. This
    module turns a teacher's OWN coaching signals *over time* (many lessons)
    into a private :class:`DevelopmentPlan`: a per-dimension TRAJECTORY (is this
    improving, holding, or slipping), a couple of growth-framed focus areas with
    one concrete next step each, and the evidence behind them. It is the
    teacher's own reflective record — never a rating, never a verdict.

  - **"...before any aggregate reaches leadership."** Leadership sometimes needs
    to see the *shape* of teaching across a school (e.g. "are we, as a school,
    giving learners enough thinking time?"). The spec is explicit that an
    aggregate may only reach leadership AFTER coaching has reached the teacher,
    and that there is no automated punitive ranking. :class:`LeadershipAggregate`
    is therefore DE-IDENTIFIED by construction: it carries NO teacher refs and
    NO per-teacher rows — only school-level distributions over a cohort — and it
    refuses to build below a k-anonymity floor. There is no code path that
    re-attaches a teacher to an aggregate figure.

Three load-bearing rules, enforced in code (not just documented):

  1. **Private + teacher-first.** A development plan belongs to the teacher; it
     is ``private`` + ``teacher_first`` like a coaching signal, and only signals
     for ONE teacher may compose it (mixing teachers raises).

  2. **No ranking, no per-teacher leadership view.** The aggregate has no teacher
     identity at all and exposes no ``rank`` / ``rating`` / ``score`` per person.
     ``refuse_per_teacher_leadership_view`` is the callable contract for "you may
     not ask this module to show leadership a named teacher's signals."

  3. **Coaching reaches the teacher first.** A plan is built directly from the
     teacher's own signals; an aggregate is built only from plans that have been
     surfaced to their teachers (``surfaced_to_teacher=True``), so leadership
     never sees a shape the teachers themselves have not yet seen.

Pure, deterministic, import-safe: no network, DB, model, or wall-clock
dependency. Identical signals in -> identical plan/aggregate out.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from .coaching import (
    CoachingSignal,
    Confidence,
    Direction,
    SignalDimension,
    employment_decision_guard,
)


# A school-level aggregate may only be built over a cohort of at least this many
# teachers — a k-anonymity floor so no individual is re-identifiable from the
# distribution. Below it, the aggregate refuses to build (privacy over insight).
_MIN_COHORT_FOR_AGGREGATE = 5

# Dimension trajectory verdicts. Longitudinal, descriptive, never a grade.
Trajectory = str  # one of the constants below.
TRAJECTORY_IMPROVING = "improving"
TRAJECTORY_STEADY = "steady"
TRAJECTORY_SLIPPING = "slipping"
TRAJECTORY_TOO_LITTLE_DATA = "too_little_data"

# Direction -> a small numeric reading used ONLY to read a within-teacher trend
# over the teacher's own lessons. It never leaves the teacher's plan and never
# compares two teachers (that would be a ranking — see the refusals below).
_DIRECTION_VALUE: dict[Direction, int] = {
    "growth_area": 0,
    "neutral": 1,
    "strength": 2,
}


class PerTeacherLeadershipViewError(RuntimeError):
    """Raised on any attempt to show leadership a named teacher's signals."""


def refuse_per_teacher_leadership_view(*_args: object, **_kwargs: object) -> "None":
    """Leadership never gets a per-teacher coaching view — a callable contract.

    The spec allows an *aggregate* to reach leadership only after coaching has
    reached the teacher, and forbids automated punitive ranking. A per-teacher,
    leadership-facing view of coaching signals is exactly the thing that ban
    exists to prevent, so this function always refuses. Leadership reads the
    de-identified :class:`LeadershipAggregate`; never a person.
    """
    raise PerTeacherLeadershipViewError(
        "Teacher growth never exposes a per-teacher coaching view to leadership. "
        "Coaching signals are private and teacher-first; leadership may see only "
        "the de-identified, cohort-level LeadershipAggregate, and only after "
        "coaching has reached the teachers themselves."
    )


@dataclass(frozen=True)
class DimensionTrajectory:
    """How one interaction dimension is moving across a teacher's own lessons.

    Descriptive and longitudinal: it reads the teacher's recent signals against
    their earlier ones. Never a score on the teacher; never compared to anyone.
    """

    dimension: SignalDimension
    trajectory: Trajectory
    latest_direction: Direction
    observations: int
    confidence: Confidence
    evidence: str


@dataclass
class DevelopmentPlan:
    """A teacher's PRIVATE, longitudinal development plan.

    Built from the teacher's own coaching signals over many lessons. Carries a
    trajectory per dimension and one or two growth-framed focus areas, each with
    a concrete next step. It is the teacher's reflective record, surfaced to them
    first; it widens only with their own consent (like a coaching signal).
    """

    teacher_ref: str
    lessons_observed: int
    trajectories: list[DimensionTrajectory] = field(default_factory=list)
    visibility: str = "teacher_first"
    private: bool = True
    # Set True once the plan has actually been surfaced to its teacher. Only
    # surfaced plans may feed a leadership aggregate (coaching-first).
    surfaced_to_teacher: bool = False

    def __post_init__(self) -> None:
        if not self.private:
            raise ValueError("A development plan is always private (teacher-first).")
        if self.visibility != "teacher_first":
            raise ValueError("Development plan visibility is fixed to teacher_first.")

    @property
    def focus_areas(self) -> list[DimensionTrajectory]:
        """The dimensions to put attention on next: anything slipping, then
        anything whose latest read is a growth area. Strengths-first framing
        means these are offered as "what to try next", never as failures."""
        slipping = [t for t in self.trajectories if t.trajectory == TRAJECTORY_SLIPPING]
        growth_now = [
            t
            for t in self.trajectories
            if t.latest_direction == "growth_area"
            and t.trajectory != TRAJECTORY_SLIPPING
        ]
        return slipping + growth_now

    @property
    def strengths(self) -> list[DimensionTrajectory]:
        return [
            t
            for t in self.trajectories
            if t.latest_direction == "strength"
            or t.trajectory == TRAJECTORY_IMPROVING
        ]

    def why_am_i_seeing_this(self) -> str:
        return (
            "This is your own development plan, built from private reflections on "
            "your lessons over time and shared with you first. It is not a rating "
            "and is not visible to anyone else unless you choose to share it."
        )

    def framing(self) -> str:
        return (
            "How your teaching is trending across recent lessons. Strengths first, "
            "then one or two things to keep building. Yours to keep or share; "
            "never a rating, never a comparison with anyone else."
        )


def _trajectory_for(samples: list[CoachingSignal]) -> Trajectory:
    """Read a within-teacher trend from earliest -> latest on one dimension.

    Compares the mean of the earlier half against the later half. Needs at least
    a few observations to say anything; otherwise reports too-little-data so the
    plan never over-claims from one lesson.
    """
    n = len(samples)
    if n < 3:
        return TRAJECTORY_TOO_LITTLE_DATA
    values = [_DIRECTION_VALUE[s.direction] for s in samples]
    half = n // 2
    earlier = values[:half]
    later = values[n - half:]
    earlier_mean = sum(earlier) / len(earlier)
    later_mean = sum(later) / len(later)
    delta = later_mean - earlier_mean
    if delta >= 0.5:
        return TRAJECTORY_IMPROVING
    if delta <= -0.5:
        return TRAJECTORY_SLIPPING
    return TRAJECTORY_STEADY


def _confidence_for(observations: int) -> Confidence:
    if observations >= 6:
        return "high"
    if observations >= 3:
        return "medium"
    return "low"


def build_development_plan(
    *,
    teacher_ref: str,
    signals: Iterable[CoachingSignal],
) -> DevelopmentPlan:
    """Build one teacher's private development plan from their signals over time.

    ``signals`` is the teacher's OWN coaching signals across many lessons, in
    chronological order (oldest first). Pure and deterministic. Raises if any
    signal belongs to a different teacher — a plan never mixes people.
    """
    if not teacher_ref:
        raise ValueError("A development plan requires a teacher_ref (opaque).")

    by_dimension: dict[SignalDimension, list[CoachingSignal]] = {}
    lesson_ids: set[str] = set()
    for sig in signals:
        if sig.teacher_ref != teacher_ref:
            raise ValueError(
                "A development plan is for ONE teacher; it never mixes signals "
                "from different teachers."
            )
        by_dimension.setdefault(sig.dimension, []).append(sig)
        lesson_ids.add(sig.lesson_id)

    trajectories: list[DimensionTrajectory] = []
    for dimension, dim_signals in by_dimension.items():
        trend = _trajectory_for(dim_signals)
        latest = dim_signals[-1]
        observations = len(dim_signals)
        trajectories.append(
            DimensionTrajectory(
                dimension=dimension,
                trajectory=trend,
                latest_direction=latest.direction,
                observations=observations,
                confidence=_confidence_for(observations),
                evidence=(
                    f"{observations} reflection(s) on {dimension} across recent "
                    f"lessons; latest reads as {latest.direction}."
                ),
            )
        )

    # Deterministic order so the plan is reproducible regardless of dict order.
    trajectories.sort(key=lambda t: t.dimension)
    return DevelopmentPlan(
        teacher_ref=teacher_ref,
        lessons_observed=len(lesson_ids),
        trajectories=trajectories,
    )


@dataclass(frozen=True)
class LeadershipAggregate:
    """A DE-IDENTIFIED, cohort-level view of teaching shape for leadership.

    Carries NO teacher refs and NO per-teacher rows — only distributions over a
    cohort. Built only from plans already surfaced to their teachers, and only
    above a k-anonymity floor, so it cannot single anyone out and never precedes
    the teacher's own view. There is no method to re-attach a teacher to a figure.
    """

    cohort_size: int
    # Per dimension: how many teachers in the cohort have this as a focus area
    # right now (a school-level shape, e.g. "wait time is a focus for many").
    focus_area_counts: dict[str, int]
    # Per dimension: how many show it as a strength (the school's strong suits).
    strength_counts: dict[str, int]

    def __post_init__(self) -> None:
        # Defend the no-identity invariant structurally: there is no place to put
        # a teacher ref, and the counts are plain dimension->int.
        for value in (*self.focus_area_counts.values(), *self.strength_counts.values()):
            if not isinstance(value, int):
                raise TypeError("Aggregate counts are plain integers, never refs.")

    def why_am_i_seeing_this(self) -> str:
        return (
            "This is a de-identified, school-level view of teaching practice "
            "across a cohort of teachers. It carries no individual teacher and is "
            "shown only after coaching has reached the teachers themselves. It is "
            "a shape to support the whole school, never a ranking of people."
        )

    def proportion_focus(self, dimension: str) -> float:
        """Share of the cohort for whom ``dimension`` is a focus area, in [0, 1]."""
        if self.cohort_size <= 0:
            return 0.0
        return round(self.focus_area_counts.get(dimension, 0) / self.cohort_size, 4)


def build_leadership_aggregate(
    plans: Iterable[DevelopmentPlan],
    *,
    min_cohort: int = _MIN_COHORT_FOR_AGGREGATE,
) -> LeadershipAggregate:
    """Aggregate development plans into a de-identified, cohort-level shape.

    Privacy is structural, not advisory:

      - Only plans **already surfaced to their teacher** are counted — leadership
        never sees a shape before the teachers have seen their own plan.
      - The cohort must clear the k-anonymity floor (``min_cohort``); otherwise
        this REFUSES (a small cohort is re-identifiable). Privacy over insight.
      - The result carries NO teacher refs — only dimension->count distributions.

    Raises on a per-teacher request via :func:`refuse_per_teacher_leadership_view`
    is NOT needed here because there is simply no parameter that admits a single
    teacher; the de-identified shape is the only thing this returns.
    """
    plan_list = list(plans)
    surfaced = [p for p in plan_list if p.surfaced_to_teacher]
    if len(surfaced) < min_cohort:
        raise PerTeacherLeadershipViewError(
            f"A leadership aggregate needs at least {min_cohort} teachers whose "
            f"plans have already been surfaced to them (k-anonymity floor); got "
            f"{len(surfaced)}. Below the floor an aggregate could single someone "
            f"out, so it is refused — privacy over insight."
        )

    focus = Counter()
    strength = Counter()
    for plan in surfaced:
        # Per teacher, count each dimension at most once (presence, not weight),
        # so one teacher with many lessons cannot dominate the distribution.
        focus.update({t.dimension for t in plan.focus_areas})
        strength.update({t.dimension for t in plan.strengths})

    return LeadershipAggregate(
        cohort_size=len(surfaced),
        focus_area_counts=dict(focus),
        strength_counts=dict(strength),
    )


def guard_no_employment_use(*_args: object, **_kwargs: object) -> "None":
    """A development plan / aggregate is never an input to an employment decision.

    Thin re-export of the B10 employment guard so callers near the growth-plan
    surface have the prohibition close to hand: nothing here auto-decides about a
    person (INVARIANT 8). Always refuses.
    """
    employment_decision_guard()
