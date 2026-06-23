"""From-scratch timetable GENERATION (B2).

The constraint solver in :mod:`app.timetable` answers a *change* — a disruption
needs a scored alternative. This module answers the larger, up-front question:
*lay out a whole timetable from nothing* — a set of teaching requirements (a
section needs N periods of a subject per week, taught by a teacher, in a room) is
packed into the week's slots.

It does NOT produce one answer. It produces the **three named alternatives** the
document calls for, each optimised on a different axis:

  - **best academic balance**  — subjects spread well across the week and the
    day (no doubling a hard subject into the last slots; even day-to-day spread);
  - **best workload balance**  — teacher load spread evenly across days, no long
    runs of consecutive periods for one teacher;
  - **best resource use**      — rooms (the RESOURCE dimension) packed tightly,
    specialist rooms used by the right subjects, fewer rooms held idle.

Every alternative is feasible by construction (no hard clash — a teacher, a
section, or a room is never double-booked), is SCORED on all three axes (so the
trade-off each one makes is visible), and is EXPLAINED (why this layout, what it
optimises, what it costs). Like every other consequential output in this module
it is **never auto-committed**: generation returns alternatives for a human to
compare and approve; committing a generated timetable to live use sits at
``execute_with_permission`` on the permission ladder (INVARIANT 8).

Pure, deterministic, dependency-free. Opaque ids + generic labels only — no PII.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Sequence

from .timetable import Period, Slot, Timetable


# ---------------------------------------------------------------------------
# Inputs: the requirements + the resources to pack
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TeachingRequirement:
    """One thing that must appear on the timetable: a section needs this many
    periods of a subject in the week, taught by a teacher.

    ``room_id`` pins a required room (a lab, a specialist room) when set;
    otherwise the generator picks from the supplied room pool to optimise
    resource use. All ids opaque; no PII.
    """

    requirement_id: str
    section_id: str
    subject_id: str
    teacher_ref: str  # opaque canonical_uuid of the assigned teacher.
    periods_per_week: int
    room_id: str | None = None  # pinned room, or None to let the generator pick.

    def __post_init__(self) -> None:
        if self.periods_per_week < 1:
            raise ValueError("periods_per_week must be >= 1.")


@dataclass(frozen=True)
class GenerationInputs:
    """Everything the generator packs into the week.

    ``slots`` is the grid of available teaching slots (weekday + period). ``rooms``
    is the pool of general rooms the generator may assign when a requirement does
    not pin one. The generator never invents a slot or a room beyond these.
    """

    institution_id: str
    requirements: list[TeachingRequirement]
    slots: list[Slot]
    rooms: list[str] = field(default_factory=list)

    def total_demand(self) -> int:
        return sum(r.periods_per_week for r in self.requirements)


# ---------------------------------------------------------------------------
# The three named axes
# ---------------------------------------------------------------------------


class GenerationAxis(str, Enum):
    """The three alternative timetables the document names."""

    ACADEMIC_BALANCE = "best_academic_balance"
    WORKLOAD_BALANCE = "best_workload_balance"
    RESOURCE_USE = "best_resource_use"


AXIS_LABELS: dict[GenerationAxis, str] = {
    GenerationAxis.ACADEMIC_BALANCE: "Best academic balance",
    GenerationAxis.WORKLOAD_BALANCE: "Best workload balance",
    GenerationAxis.RESOURCE_USE: "Best resource use",
}


# ---------------------------------------------------------------------------
# Scoring on all three dimensions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerationScores:
    """The three scores every generated timetable carries, each in [0, 1].

    Holding ALL THREE on every alternative is the point: the academic-balance
    timetable still reports its workload and resource scores, so the trade-off it
    makes is explicit and comparable.
    """

    academic_balance: float
    workload_balance: float
    resource_use: float

    def for_axis(self, axis: GenerationAxis) -> float:
        return {
            GenerationAxis.ACADEMIC_BALANCE: self.academic_balance,
            GenerationAxis.WORKLOAD_BALANCE: self.workload_balance,
            GenerationAxis.RESOURCE_USE: self.resource_use,
        }[axis]


def _spread_score(counts: Sequence[int]) -> float:
    """A 0..1 evenness score for a list of per-bucket counts: 1.0 when perfectly
    even, falling as the spread becomes lumpy. Empty / single bucket -> 1.0."""
    if len(counts) <= 1:
        return 1.0
    total = sum(counts)
    if total == 0:
        return 1.0
    mean = total / len(counts)
    # Mean absolute deviation normalised by the mean, clamped into [0, 1].
    mad = sum(abs(c - mean) for c in counts) / len(counts)
    return round(max(0.0, 1.0 - (mad / mean if mean else 0.0)), 4)


def score_academic_balance(periods: Sequence[Period]) -> float:
    """How evenly each subject is spread across weekdays (no clustering a subject
    into a couple of days), averaged over subjects.
    """
    by_subject: dict[str, dict[int, int]] = {}
    weekdays = sorted({p.slot.weekday for p in periods})
    for p in periods:
        day_counts = by_subject.setdefault(p.subject_id, {w: 0 for w in weekdays})
        day_counts[p.slot.weekday] += 1
    if not by_subject:
        return 1.0
    per_subject = [_spread_score(list(d.values())) for d in by_subject.values()]
    return round(sum(per_subject) / len(per_subject), 4)


def score_workload_balance(periods: Sequence[Period]) -> float:
    """How evenly each teacher's load is spread across weekdays (no teacher with
    all their periods bunched on one day), averaged over teachers.
    """
    by_teacher: dict[str, dict[int, int]] = {}
    weekdays = sorted({p.slot.weekday for p in periods})
    for p in periods:
        day_counts = by_teacher.setdefault(p.teacher_ref, {w: 0 for w in weekdays})
        day_counts[p.slot.weekday] += 1
    if not by_teacher:
        return 1.0
    per_teacher = [_spread_score(list(d.values())) for d in by_teacher.values()]
    return round(sum(per_teacher) / len(per_teacher), 4)


def score_resource_use(periods: Sequence[Period], room_pool: Sequence[str]) -> float:
    """RESOURCE-use score: how tightly rooms are packed.

    Reward concentrating periods into fewer rooms (a room held open for one
    period a week is wasteful) while never breaching the hard one-room-per-slot
    rule (the generator guarantees that upstream). Computed as the mean
    utilisation of the rooms actually used: total room-periods / (rooms used ×
    busiest room's load). 1.0 when every used room is as busy as the busiest.
    """
    roomed = [p for p in periods if p.room_id is not None]
    if not roomed:
        return 1.0
    load: dict[str, int] = {}
    for p in roomed:
        load[p.room_id] = load.get(p.room_id, 0) + 1  # type: ignore[index]
    rooms_used = len(load)
    busiest = max(load.values())
    utilisation = sum(load.values()) / (rooms_used * busiest)
    return round(utilisation, 4)


# ---------------------------------------------------------------------------
# A generated, scored, approvable alternative
# ---------------------------------------------------------------------------


@dataclass
class GeneratedTimetable:
    """One whole timetable generated from scratch, scored on all three axes.

    NEVER auto-committed. ``ladder_stage`` is fixed to
    ``execute_with_permission`` and ``is_consequential`` is always True — putting
    a generated timetable into live use affects every student, teacher, and room,
    so it waits for explicit approval (INVARIANT 8). :func:`commit_generated`
    is the separate, human-gated step.
    """

    axis: GenerationAxis
    institution_id: str
    periods: list[Period]
    scores: GenerationScores
    unplaced: list[str]  # requirement_ids that could not be fully placed.
    owner_role: str = "coordinator"
    owner_ref: str = ""
    ladder_stage: str = "execute_with_permission"
    is_consequential: bool = True
    committed: bool = False  # invariant: the generator never sets this True.

    @property
    def axis_label(self) -> str:
        return AXIS_LABELS[self.axis]

    @property
    def headline_score(self) -> float:
        """The score on the axis this alternative optimises for."""
        return self.scores.for_axis(self.axis)

    @property
    def fully_placed(self) -> bool:
        return not self.unplaced

    @property
    def confidence_band(self) -> Literal["low", "medium", "high"]:
        if not self.fully_placed:
            return "low"
        if self.headline_score >= 0.8:
            return "high"
        if self.headline_score >= 0.5:
            return "medium"
        return "low"

    @property
    def why(self) -> str:
        return (
            f"Generated from scratch to optimise {self.axis_label.lower()}: "
            f"{len(self.periods)} period(s) placed across the week. Scored on all "
            "three axes so the trade-off is visible; surfaced for your approval — "
            "a generated timetable is never put into live use on its own."
        )

    @property
    def evidence(self) -> list[str]:
        lines = [
            f"academic balance {self.scores.academic_balance:.2f}",
            f"workload balance {self.scores.workload_balance:.2f}",
            f"resource use {self.scores.resource_use:.2f}",
        ]
        if self.unplaced:
            lines.append(
                f"{len(self.unplaced)} requirement(s) could not be fully placed "
                "with the supplied slots/rooms — widen the grid or pool"
            )
        return lines

    @property
    def consequence_of_committing(self) -> str:
        if not self.fully_placed:
            return (
                "Not ready to commit: some requirements are unplaced. Committing "
                "would leave teaching demand uncovered. Shown so the gap is visible."
            )
        return (
            "Committing makes this the live timetable for every affected section, "
            "teacher, and room. A human approves; the generator never commits."
        )

    def as_timetable(self) -> Timetable:
        """A live-shaped :class:`Timetable` view (still uncommitted)."""
        return Timetable(institution_id=self.institution_id, periods=list(self.periods))


# ---------------------------------------------------------------------------
# The generator
# ---------------------------------------------------------------------------


class TimetableGenerator:
    """Packs teaching requirements into the week's slots from scratch and returns
    the three named alternatives — never committing any of them.

    The generator is greedy + deterministic: for each axis it orders placement to
    favour that axis, places every required period into a feasible slot+room (no
    teacher / section / room clash), and scores the result on all three axes. It
    is intentionally simple and explainable rather than an opaque optimiser; the
    human comparing the three alternatives is the decision-maker.
    """

    def __init__(self, *, owner_role: str = "coordinator", owner_ref: str = "") -> None:
        self._owner_role = owner_role
        self._owner_ref = owner_ref

    def generate(self, inputs: GenerationInputs) -> list[GeneratedTimetable]:
        """Generate one :class:`GeneratedTimetable` per axis, ordered by the axis
        enum. Each is feasible by construction and scored on all three axes.
        """
        return [self.generate_for_axis(inputs, axis) for axis in GenerationAxis]

    def generate_for_axis(
        self, inputs: GenerationInputs, axis: GenerationAxis
    ) -> GeneratedTimetable:
        placed, unplaced = self._pack(inputs, axis)
        scores = GenerationScores(
            academic_balance=score_academic_balance(placed),
            workload_balance=score_workload_balance(placed),
            resource_use=score_resource_use(placed, inputs.rooms),
        )
        return GeneratedTimetable(
            axis=axis,
            institution_id=inputs.institution_id,
            periods=placed,
            scores=scores,
            unplaced=unplaced,
            owner_role=self._owner_role,
            owner_ref=self._owner_ref,
        )

    # -- placement ----------------------------------------------------------

    def _pack(
        self, inputs: GenerationInputs, axis: GenerationAxis
    ) -> tuple[list[Period], list[str]]:
        """Greedy, feasible placement of every required period.

        Tracks per-slot occupancy of teachers, sections, and rooms so no hard
        clash is ever produced. The slot ORDER each placement considers depends
        on the axis, which is what bends the result toward that axis's score.
        """
        placed: list[Period] = []
        unplaced: list[str] = []

        teacher_busy: set[tuple[str, Slot]] = set()
        section_busy: set[tuple[str, Slot]] = set()
        room_busy: set[tuple[str, Slot]] = set()
        # Per-teacher per-day load, for workload-aware slot ordering.
        teacher_day_load: dict[tuple[str, int], int] = {}
        # Per-subject per-day load, for academic-spread slot ordering.
        subject_day_load: dict[tuple[str, int], int] = {}
        # Rooms already opened, for resource-tight room selection.
        opened_rooms: dict[str, int] = {}

        # Place larger requirements first so the scarce slots go to the biggest
        # demand; stable by id for determinism.
        reqs = sorted(
            inputs.requirements,
            key=lambda r: (-r.periods_per_week, r.requirement_id),
        )

        for req in reqs:
            placed_count = 0
            for _ in range(req.periods_per_week):
                slot = self._pick_slot(
                    req,
                    inputs.slots,
                    axis,
                    teacher_busy,
                    section_busy,
                    teacher_day_load,
                    subject_day_load,
                )
                if slot is None:
                    break
                room = self._pick_room(
                    req, slot, inputs.rooms, axis, room_busy, opened_rooms
                )
                period = Period(
                    period_id=f"gen:{req.requirement_id}:{placed_count + 1}",
                    section_id=req.section_id,
                    slot=slot,
                    subject_id=req.subject_id,
                    teacher_ref=req.teacher_ref,
                    room_id=room,
                )
                placed.append(period)
                teacher_busy.add((req.teacher_ref, slot))
                section_busy.add((req.section_id, slot))
                if room is not None:
                    room_busy.add((room, slot))
                    opened_rooms[room] = opened_rooms.get(room, 0) + 1
                teacher_day_load[(req.teacher_ref, slot.weekday)] = (
                    teacher_day_load.get((req.teacher_ref, slot.weekday), 0) + 1
                )
                subject_day_load[(req.subject_id, slot.weekday)] = (
                    subject_day_load.get((req.subject_id, slot.weekday), 0) + 1
                )
                placed_count += 1
            if placed_count < req.periods_per_week:
                unplaced.append(req.requirement_id)
        return placed, unplaced

    def _pick_slot(
        self,
        req: TeachingRequirement,
        slots: Sequence[Slot],
        axis: GenerationAxis,
        teacher_busy: set[tuple[str, Slot]],
        section_busy: set[tuple[str, Slot]],
        teacher_day_load: dict[tuple[str, int], int],
        subject_day_load: dict[tuple[str, int], int],
    ) -> Slot | None:
        """Choose a feasible slot for one period of ``req``, ordered by the axis.

        Feasible = the teacher and the section are both free in it. The ORDERING
        of feasible slots is what bends the layout toward the axis:
          - workload: prefer the day where this teacher is least loaded;
          - academic: prefer the day where this subject is least present, and
            earlier periods (hard subjects earlier);
          - resource: leave the slot order natural so room packing dominates.
        """
        feasible = [
            s
            for s in slots
            if (req.teacher_ref, s) not in teacher_busy
            and (req.section_id, s) not in section_busy
        ]
        if not feasible:
            return None

        if axis is GenerationAxis.WORKLOAD_BALANCE:
            feasible.sort(
                key=lambda s: (
                    teacher_day_load.get((req.teacher_ref, s.weekday), 0),
                    s.weekday,
                    s.period,
                )
            )
        elif axis is GenerationAxis.ACADEMIC_BALANCE:
            feasible.sort(
                key=lambda s: (
                    subject_day_load.get((req.subject_id, s.weekday), 0),
                    s.period,  # earlier periods preferred.
                    s.weekday,
                )
            )
        else:  # RESOURCE_USE: natural slot order; room packing carries this axis.
            feasible.sort(key=lambda s: (s.weekday, s.period))
        return feasible[0]

    def _pick_room(
        self,
        req: TeachingRequirement,
        slot: Slot,
        rooms: Sequence[str],
        axis: GenerationAxis,
        room_busy: set[tuple[str, Slot]],
        opened_rooms: dict[str, int],
    ) -> str | None:
        """Choose a room for the period at ``slot``.

        A pinned room is honoured when free (a lab must be the lab); if pinned but
        busy this slot, the period is roomless rather than clashing. From the
        pool, the RESOURCE axis prefers an already-opened room (pack tight); the
        other axes take the first free room in pool order.
        """
        if req.room_id is not None:
            return req.room_id if (req.room_id, slot) not in room_busy else None
        free = [r for r in rooms if (r, slot) not in room_busy]
        if not free:
            return None
        if axis is GenerationAxis.RESOURCE_USE:
            # Prefer the most-used already-opened free room to pack tightly.
            free.sort(key=lambda r: (-opened_rooms.get(r, 0), r))
        else:
            free.sort()
        return free[0]


def commit_generated(
    generated: GeneratedTimetable,
    *,
    approved_by: str | None,
) -> Timetable:
    """Commit an approved generated timetable into live use — the SEPARATE,
    explicit, human-gated step.

    Refuses without an ``approved_by`` (an opaque human ref): standing up a whole
    timetable is consequential and never auto-fires (INVARIANT 8). Refuses a
    not-fully-placed alternative (it would leave teaching demand uncovered). The
    generator never calls this; only an approval workflow does, after a human
    decision.
    """
    if not approved_by:
        raise PermissionError(
            "Committing a generated timetable is consequential and requires "
            "explicit human approval (approved_by). The generator never commits."
        )
    if not generated.fully_placed:
        raise ValueError(
            "cannot commit a timetable with unplaced requirements; widen the "
            "slot grid or room pool first."
        )
    generated.committed = True
    return generated.as_timetable()
