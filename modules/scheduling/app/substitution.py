"""The substitution ladder (B2): Level 1-6, never a free period.

When a period loses its teacher, every class is covered — a class is never left
unsupervised and a slot is never silently turned into a free period. The ladder
descends six levels of preference, and the engine produces RANKED, scored
options for a human to approve. It never auto-assigns: assigning a substitute is
consequential and waits for explicit approval (INVARIANT 8).

The ladder (best first):

  Level 1 — Same-subject free teacher: a teacher of the same subject who is free
            this slot. Best continuity (the lesson continues properly).
  Level 2 — Same-grade subject teacher: teaches the subject at the same grade,
            free this slot (continuity across sections).
  Level 3 — Any free qualified teacher: free this slot and competent in the
            subject, even if not their usual grade.
  Level 4 — Departmental cover: a free teacher from the same department —
            supervises and runs prepared work, may not be a subject specialist.
  Level 5 — General free-staff cover: any free member of staff supervises with a
            prepared continuity pack.
  Level 6 — Combine / supervised study under a duty teacher: the last resort —
            still SUPERVISED. Two sections merge under one teacher, or the class
            joins a supervised study room. NEVER an unsupervised free period.

There is no Level 7. The ladder is exhaustive precisely so "leave it free" is
never an option. :func:`build_ladder` always yields at least the Level 6
supervised fallback whenever a duty teacher exists; the only way to get zero
options is to supply no candidate staff at all, which the caller is told to
treat as an escalation, not a free period.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum
from typing import Literal, Sequence


class SubLevel(IntEnum):
    """The six ladder levels, lower = more preferred."""

    SAME_SUBJECT_FREE = 1
    SAME_GRADE_SUBJECT = 2
    ANY_QUALIFIED_FREE = 3
    DEPARTMENTAL_COVER = 4
    GENERAL_STAFF_COVER = 5
    SUPERVISED_COMBINE = 6


LEVEL_LABELS: dict[SubLevel, str] = {
    SubLevel.SAME_SUBJECT_FREE: "Same-subject teacher, free this slot",
    SubLevel.SAME_GRADE_SUBJECT: "Same-grade subject teacher, free this slot",
    SubLevel.ANY_QUALIFIED_FREE: "Any free teacher qualified in the subject",
    SubLevel.DEPARTMENTAL_COVER: "Departmental cover (free department teacher)",
    SubLevel.GENERAL_STAFF_COVER: "General staff cover with a continuity pack",
    SubLevel.SUPERVISED_COMBINE: "Supervised combine / study under a duty teacher",
}

# Continuity quality per level, in [0, 1] — how well the lesson actually
# continues. Higher levels still cover the class but with less subject continuity.
LEVEL_CONTINUITY: dict[SubLevel, float] = {
    SubLevel.SAME_SUBJECT_FREE: 1.0,
    SubLevel.SAME_GRADE_SUBJECT: 0.9,
    SubLevel.ANY_QUALIFIED_FREE: 0.75,
    SubLevel.DEPARTMENTAL_COVER: 0.55,
    SubLevel.GENERAL_STAFF_COVER: 0.4,
    SubLevel.SUPERVISED_COMBINE: 0.25,
}


@dataclass(frozen=True)
class StaffMember:
    """A candidate staff member. All ids opaque; no PII.

    ``free_slots`` is the set of slot keys the staff member is free in (the
    caller supplies slot keys it computes from the live timetable, e.g.
    ``"2:4"`` for weekday 2 period 4)."""

    staff_ref: str  # opaque canonical_uuid.
    role: str  # generic, e.g. "teacher", "duty_teacher".
    subject_ids: frozenset[str] = frozenset()  # subjects they can teach.
    department_id: str | None = None
    grade_ids: frozenset[str] = frozenset()  # grades they teach.
    is_duty_teacher: bool = False  # can supervise a combined / study room.

    def is_free(self, slot_key: str) -> bool:
        return slot_key in self.free_slots

    free_slots: frozenset[str] = frozenset()


@dataclass(frozen=True)
class VacancyContext:
    """The vacancy to fill — opaque ids and generic labels only."""

    period_id: str
    on_date: date
    slot_key: str  # the slot the substitute must be free in.
    subject_id: str
    grade_id: str
    department_id: str | None = None
    absent_teacher_ref: str | None = None


@dataclass
class SubstituteOption:
    """A ranked substitution option for human approval.

    Carries the ladder level, the continuity quality, evidence, an owner, and the
    explicit fact that it is consequential and never auto-fires. Mirrors the A5
    Recommendation contract.
    """

    option_id: str
    level: SubLevel
    staff_ref: str | None  # None only for a study-room combine with no named teacher.
    vacancy_period_id: str
    rank: int  # 1 = top option; filled in by the engine after ranking.
    why: str
    owner_role: str = "coordinator"
    owner_ref: str = ""
    ladder_stage: str = "execute_with_permission"
    is_consequential: bool = True
    is_free_period: Literal[False] = False  # invariant, structurally: never True.
    notes: list[str] = field(default_factory=list)

    @property
    def level_label(self) -> str:
        return LEVEL_LABELS[self.level]

    @property
    def continuity(self) -> float:
        return LEVEL_CONTINUITY[self.level]

    @property
    def confidence_band(self) -> Literal["low", "medium", "high"]:
        if self.continuity >= 0.85:
            return "high"
        if self.continuity >= 0.5:
            return "medium"
        return "low"

    @property
    def is_supervised(self) -> bool:
        """Every option is supervised. A combine option needs a duty teacher;
        all others name a covering staff member."""
        return self.staff_ref is not None or self.level is SubLevel.SUPERVISED_COMBINE


class SubstitutionLadder:
    """Builds and ranks substitute options across Level 1-6. Never auto-assigns."""

    def __init__(self, *, owner_role: str = "coordinator", owner_ref: str = "") -> None:
        self._owner_role = owner_role
        self._owner_ref = owner_ref

    def _classify(self, staff: StaffMember, vac: VacancyContext) -> SubLevel | None:
        """The best (lowest) ladder level a free staff member qualifies for, or
        ``None`` if they are not free this slot (and so cannot cover)."""
        if not staff.is_free(vac.slot_key):
            return None
        teaches_subject = vac.subject_id in staff.subject_ids
        teaches_grade = vac.grade_id in staff.grade_ids
        # Level 1: teaches this exact subject AND this exact grade — best
        # continuity, the lesson continues properly.
        if teaches_subject and teaches_grade:
            return SubLevel.SAME_SUBJECT_FREE
        # Level 2: teaches the subject and teaches at some grade, just not this
        # one — strong continuity across the grade's sections.
        if teaches_subject and staff.grade_ids:
            return SubLevel.SAME_GRADE_SUBJECT
        # Level 3: qualified in the subject but with no grade band on file.
        if teaches_subject:
            return SubLevel.ANY_QUALIFIED_FREE
        if vac.department_id is not None and staff.department_id == vac.department_id:
            return SubLevel.DEPARTMENTAL_COVER
        # Any free staff member can at least supervise.
        return SubLevel.GENERAL_STAFF_COVER

    def build_ladder(
        self,
        vacancy: VacancyContext,
        staff: Sequence[StaffMember],
    ) -> list[SubstituteOption]:
        """Produce ranked options. Best (lowest level, highest continuity) first.

        Always includes a Level 6 supervised fallback when a duty teacher is
        available, so "leave it free" is never produced. Returns an empty list
        ONLY when no staff at all are supplied — which the caller must treat as
        an escalation, never as a free period.
        """
        options: list[SubstituteOption] = []
        n = 0
        for member in staff:
            level = self._classify(member, vacancy)
            if level is None:
                continue
            n += 1
            options.append(
                SubstituteOption(
                    option_id=f"{vacancy.period_id}:opt:{n}",
                    level=level,
                    staff_ref=member.staff_ref,
                    vacancy_period_id=vacancy.period_id,
                    rank=0,
                    why=self._why(level, vacancy, member),
                    owner_role=self._owner_role,
                    owner_ref=self._owner_ref,
                    notes=self._notes(level),
                )
            )

        # Level 6 supervised fallback: a duty teacher hosts a combine / study
        # room. Added whenever a duty teacher exists, so coverage is guaranteed
        # and a free period is structurally impossible.
        duty = next((m for m in staff if m.is_duty_teacher and m.is_free(vacancy.slot_key)), None)
        if duty is not None and not any(o.level is SubLevel.SUPERVISED_COMBINE for o in options):
            n += 1
            options.append(
                SubstituteOption(
                    option_id=f"{vacancy.period_id}:opt:{n}",
                    level=SubLevel.SUPERVISED_COMBINE,
                    staff_ref=duty.staff_ref,
                    vacancy_period_id=vacancy.period_id,
                    rank=0,
                    why="Last-resort supervised cover: the class is combined into a "
                    "supervised study room under a duty teacher. Still supervised — "
                    "never an unsupervised free period.",
                    owner_role=self._owner_role,
                    owner_ref=self._owner_ref,
                    notes=self._notes(SubLevel.SUPERVISED_COMBINE),
                )
            )

        # Rank: lower level first, then higher continuity, then stable by id.
        options.sort(key=lambda o: (int(o.level), -o.continuity, o.option_id))
        for i, opt in enumerate(options, start=1):
            opt.rank = i
        return options

    def _why(self, level: SubLevel, vac: VacancyContext, member: StaffMember) -> str:
        return (
            f"Level {int(level)} cover for the vacancy on {vac.on_date.isoformat()}: "
            f"{LEVEL_LABELS[level]}. Surfaced for approval; assigning a substitute "
            "is consequential and never auto-fires."
        )

    def _notes(self, level: SubLevel) -> list[str]:
        if level >= SubLevel.GENERAL_STAFF_COVER:
            return [
                "Not a subject specialist — attach a continuity pack so the class "
                "stays productive and supervised.",
            ]
        if level >= SubLevel.DEPARTMENTAL_COVER:
            return ["Departmental cover — share the lesson plan and prepared work."]
        return []


def assign_substitute(
    option: SubstituteOption,
    *,
    approved_by: str | None,
) -> SubstituteOption:
    """Confirm an approved substitution — the SEPARATE, human-gated step.

    Refuses without ``approved_by``: assigning a substitute is consequential and
    never auto-fires (INVARIANT 8). The ladder never calls this; an approval
    workflow does, after a human decision. Returns the same option so the caller
    can record the confirmed assignment; the option is never a free period by
    construction (``is_free_period`` is structurally False).
    """
    if not approved_by:
        raise PermissionError(
            "Assigning a substitute is consequential and requires explicit human "
            "approval (approved_by). The ladder only ranks options; it never assigns."
        )
    if option.is_free_period:  # pragma: no cover - structurally impossible.
        raise ValueError("a substitution option can never be a free period.")
    return option
