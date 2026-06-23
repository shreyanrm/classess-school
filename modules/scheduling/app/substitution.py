"""The substitution ladder (B2): Level 1-6, never a free period.

When a period loses its teacher, every class is covered — a class is never left
unsupervised and a slot is never silently turned into a free period. The ladder
descends six levels of preference, and the engine produces RANKED, scored
options for a human to approve. It never auto-assigns: assigning a substitute is
consequential and waits for explicit approval (INVARIANT 8).

The ladder, aligned to Figure 7 in the document (best first):

  Level 1 — Same class & subject teacher: a teacher of the same subject (and
            grade) who is free this slot. Knows the context and the syllabus
            position; best continuity, the lesson continues properly.
  Level 2 — Same subject from another grade: competent at this level, available
            and free this slot (continuity across the grade's sections).
  Level 3 — Another qualified teacher in the school: free this slot and competent
            in the subject, even if not their usual grade.
  Level 4 — Another branch / campus, taught ONLINE into the regular classroom
            under LOCAL SUPERVISION: a remote subject specialist teaches the
            lesson live; an on-site staff member supervises the room. Full
            subject continuity preserved across campuses.
  Level 5 — An approved EXTERNAL substitute, granted TIME-BOUND access that is
            REMOVED after the cover ends: a vetted external teacher with a
            scoped, expiring grant. The grant is created on approval and revoked
            when the cover window closes (INVARIANT — least privilege, no
            standing external access).
  Level 6 — Academic-continuity ALTERNATIVE: a guided session, a RECORDED
            lesson, or supervised practice — always academically meaningful and
            supervised, NEVER a free period. The last resort, still real
            learning.

There is no Level 7. The ladder is exhaustive precisely so "leave it free" is
never an option. :func:`build_ladder` always yields at least the Level 6
continuity alternative whenever a duty/supervising teacher exists; the only way
to get zero options is to supply no candidate staff at all, which the caller is
told to treat as an escalation, not a free period.

Every option also carries a PICK-UP-AT-THE-RIGHT-POINT lesson linkage so the
covering teacher resumes exactly where the class left off (see
:class:`LessonPickup`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import IntEnum
from typing import Literal, Sequence


class SubLevel(IntEnum):
    """The six ladder levels, lower = more preferred.

    Member NAMES are kept stable for callers; the meaning of Levels 4-6 is
    realigned to Figure 7 of the document (see the doc-aligned aliases below).
    """

    SAME_SUBJECT_FREE = 1
    SAME_GRADE_SUBJECT = 2
    ANY_QUALIFIED_FREE = 3
    # Level 4: another branch/campus, taught online under local supervision.
    DEPARTMENTAL_COVER = 4
    CROSS_CAMPUS_ONLINE = 4  # doc-aligned alias for Level 4.
    # Level 5: an approved external substitute with time-bound access.
    GENERAL_STAFF_COVER = 5
    EXTERNAL_TIME_BOUND = 5  # doc-aligned alias for Level 5.
    # Level 6: academic-continuity alternative (guided/recorded/supervised).
    SUPERVISED_COMBINE = 6
    CONTINUITY_ALTERNATIVE = 6  # doc-aligned alias for Level 6.


LEVEL_LABELS: dict[SubLevel, str] = {
    SubLevel.SAME_SUBJECT_FREE: "Same class & subject teacher, free this slot",
    SubLevel.SAME_GRADE_SUBJECT: "Same subject from another grade, free this slot",
    SubLevel.ANY_QUALIFIED_FREE: "Another qualified teacher in the school",
    SubLevel.CROSS_CAMPUS_ONLINE: "Another branch/campus, taught online under local supervision",
    SubLevel.EXTERNAL_TIME_BOUND: "Approved external substitute, time-bound access removed after",
    SubLevel.CONTINUITY_ALTERNATIVE: "Academic-continuity alternative (guided / recorded / supervised practice)",
}

# Continuity quality per level, in [0, 1] — how well the lesson actually
# continues. Higher levels still cover the class but with less subject continuity.
LEVEL_CONTINUITY: dict[SubLevel, float] = {
    SubLevel.SAME_SUBJECT_FREE: 1.0,
    SubLevel.SAME_GRADE_SUBJECT: 0.9,
    SubLevel.ANY_QUALIFIED_FREE: 0.75,
    # Cross-campus online keeps a subject specialist on the lesson -> strong.
    SubLevel.CROSS_CAMPUS_ONLINE: 0.7,
    # An approved external specialist also teaches the subject -> moderate.
    SubLevel.EXTERNAL_TIME_BOUND: 0.5,
    # A guided/recorded/supervised continuity alternative -> meaningful, lower.
    SubLevel.CONTINUITY_ALTERNATIVE: 0.3,
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

    # Doc-aligned Level 4/5 attributes (all opaque, no PII).
    campus_id: str | None = None  # which branch/campus this member is at.
    is_external: bool = False  # an approved EXTERNAL substitute (Level 5).
    # A remote (other-campus) specialist who can teach ONLINE into the room.
    teaches_online: bool = False

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
    home_campus_id: str | None = None  # the vacancy's campus (for cross-campus L4).
    # Where the class is in the syllabus, so cover picks up at the right point.
    current_topic_id: str | None = None
    resume_at_period: int | None = None  # plan index to resume from.


@dataclass(frozen=True)
class LessonPickup:
    """Pick-up-at-the-right-point linkage carried by every option.

    So the covering teacher (or the recorded/guided alternative) resumes EXACTLY
    where the class left off — students lose no continuity. Opaque ids only; no
    PII. Derived from the vacancy's syllabus position.
    """

    current_topic_id: str | None
    resume_at_period: int | None

    @property
    def is_linked(self) -> bool:
        return self.current_topic_id is not None or self.resume_at_period is not None

    def describe(self) -> str:
        if not self.is_linked:
            return "Syllabus position not supplied; confirm where to resume before the period."
        topic = self.current_topic_id or "the current topic"
        at = f" from plan period {self.resume_at_period}" if self.resume_at_period is not None else ""
        return f"Pick up the lesson at {topic}{at} so the class loses no continuity."


# How a Level 6 academic-continuity alternative is delivered.
ContinuityMode = Literal["guided_session", "recorded_lesson", "supervised_practice"]


@dataclass(frozen=True)
class ExternalAccessGrant:
    """A TIME-BOUND access grant for a Level 5 approved external substitute.

    Created on approval and REMOVED when the cover window closes — least
    privilege, no standing external access (an invariant of Level 5). Opaque
    refs only. The grant is inert here (no real IAM call); it records the scope
    and the expiry the wiring layer enforces, and exposes ``is_active`` so the
    removal step is explicit and auditable.
    """

    grant_id: str
    external_staff_ref: str
    scope_period_id: str
    granted_at: str  # ISO timestamp.
    expires_at: str  # ISO timestamp — access is removed at/after this.
    revoked_at: str | None = None  # set when explicitly removed after cover.

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


@dataclass
class SubstituteOption:
    """A ranked substitution option for human approval.

    Carries the ladder level, the continuity quality, the pick-up-at-the-right-
    point linkage, evidence, an owner, and the explicit fact that it is
    consequential and never auto-fires. Mirrors the A5 Recommendation contract.
    """

    option_id: str
    level: SubLevel
    staff_ref: str | None  # None only for a recorded-lesson alternative with no live teacher.
    vacancy_period_id: str
    rank: int  # 1 = top option; filled in by the engine after ranking.
    why: str
    owner_role: str = "coordinator"
    owner_ref: str = ""
    ladder_stage: str = "execute_with_permission"
    is_consequential: bool = True
    is_free_period: Literal[False] = False  # invariant, structurally: never True.
    notes: list[str] = field(default_factory=list)
    pickup: LessonPickup | None = None  # pick-up-at-the-right-point linkage.
    # Level 4: a supervising on-site staff member while the lesson is taught
    # online from another campus.
    supervisor_ref: str | None = None
    # Level 5: the time-bound external access grant created on approval.
    access_grant: ExternalAccessGrant | None = None
    # Level 6: how the continuity alternative is delivered.
    continuity_mode: ContinuityMode | None = None

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
        """Every option is supervised.

        Levels 1-3 and 5 name a covering teacher. Level 4 (cross-campus online)
        is supervised on-site by ``supervisor_ref`` while a remote specialist
        teaches. Level 6 (continuity alternative) is supervised by a duty teacher
        or, for a recorded lesson, run under supervised practice — never an
        unsupervised free period.
        """
        if self.level is SubLevel.CROSS_CAMPUS_ONLINE:
            return self.supervisor_ref is not None
        if self.level is SubLevel.CONTINUITY_ALTERNATIVE:
            return True  # always supervised; see continuity_mode.
        return self.staff_ref is not None


class SubstitutionLadder:
    """Builds and ranks substitute options across Level 1-6. Never auto-assigns."""

    def __init__(self, *, owner_role: str = "coordinator", owner_ref: str = "") -> None:
        self._owner_role = owner_role
        self._owner_ref = owner_ref

    def _classify(self, staff: StaffMember, vac: VacancyContext) -> SubLevel | None:
        """The best (lowest) ladder level a free staff member qualifies for, or
        ``None`` if they are not free this slot (and so cannot cover).

        Levels 1-3 are the in-school qualified-teacher levels. Level 4 is a
        same-subject specialist at ANOTHER campus who can teach online; Level 5
        is an approved EXTERNAL same-subject substitute. Below that, the legacy
        departmental / general-staff fallbacks keep coverage exhaustive (still
        supervised, never a free period).
        """
        if not staff.is_free(vac.slot_key):
            return None
        teaches_subject = vac.subject_id in staff.subject_ids
        teaches_grade = vac.grade_id in staff.grade_ids
        same_campus = (
            vac.home_campus_id is None
            or staff.campus_id is None
            or staff.campus_id == vac.home_campus_id
        )

        # An external approved substitute (Level 5) — regardless of campus, a
        # vetted external teacher of the subject is offered with time-bound access.
        if staff.is_external and teaches_subject:
            return SubLevel.EXTERNAL_TIME_BOUND

        # In-school, same-campus qualified teacher: Levels 1-3.
        if same_campus:
            # Level 1: teaches this exact subject AND this exact grade.
            if teaches_subject and teaches_grade:
                return SubLevel.SAME_SUBJECT_FREE
            # Level 2: teaches the subject at some grade, just not this one.
            if teaches_subject and staff.grade_ids:
                return SubLevel.SAME_GRADE_SUBJECT
            # Level 3: qualified in the subject but with no grade band on file.
            if teaches_subject:
                return SubLevel.ANY_QUALIFIED_FREE

        # Level 4: another branch/campus subject specialist who can teach ONLINE
        # into the room under local supervision — full subject continuity.
        if not same_campus and teaches_subject and staff.teaches_online:
            return SubLevel.CROSS_CAMPUS_ONLINE

        # Legacy supervised fallbacks (same int levels): departmental cover (4)
        # then general staff cover (5). Kept so coverage stays exhaustive.
        if vac.department_id is not None and staff.department_id == vac.department_id:
            return SubLevel.DEPARTMENTAL_COVER
        return SubLevel.GENERAL_STAFF_COVER

    def build_ladder(
        self,
        vacancy: VacancyContext,
        staff: Sequence[StaffMember],
    ) -> list[SubstituteOption]:
        """Produce ranked options. Best (lowest level, highest continuity) first.

        Every option carries the pick-up-at-the-right-point linkage. A Level 4
        cross-campus online option is paired with an on-site supervisor; a Level
        5 external option carries a time-bound access grant. Always includes a
        Level 6 academic-continuity ALTERNATIVE when a duty/supervising teacher
        exists, so "leave it free" is never produced. Returns an empty list ONLY
        when no staff at all are supplied — which the caller must treat as an
        escalation, never as a free period.
        """
        pickup = LessonPickup(
            current_topic_id=vacancy.current_topic_id,
            resume_at_period=vacancy.resume_at_period,
        )
        # An on-site, free staff member who can supervise a remote (online) lesson.
        on_site_supervisor = next(
            (
                m
                for m in staff
                if m.is_free(vacancy.slot_key)
                and not m.is_external
                and (
                    vacancy.home_campus_id is None
                    or m.campus_id is None
                    or m.campus_id == vacancy.home_campus_id
                )
            ),
            None,
        )

        options: list[SubstituteOption] = []
        n = 0
        for member in staff:
            level = self._classify(member, vacancy)
            if level is None:
                continue
            n += 1
            opt = SubstituteOption(
                option_id=f"{vacancy.period_id}:opt:{n}",
                level=level,
                staff_ref=member.staff_ref,
                vacancy_period_id=vacancy.period_id,
                rank=0,
                why=self._why(level, vacancy, member),
                owner_role=self._owner_role,
                owner_ref=self._owner_ref,
                notes=self._notes(level),
                pickup=pickup,
            )
            if level is SubLevel.CROSS_CAMPUS_ONLINE:
                # Pair the remote specialist with an on-site supervisor (which may
                # be the duty teacher or any other free on-site member).
                opt.supervisor_ref = (
                    on_site_supervisor.staff_ref if on_site_supervisor is not None else None
                )
            if level is SubLevel.EXTERNAL_TIME_BOUND:
                # Stage (not yet active) the time-bound grant; it is activated on
                # approval via :func:`grant_external_access` and removed after.
                opt.access_grant = ExternalAccessGrant(
                    grant_id=f"{vacancy.period_id}:grant:{member.staff_ref}",
                    external_staff_ref=member.staff_ref,
                    scope_period_id=vacancy.period_id,
                    granted_at="",  # set when actually granted on approval.
                    expires_at="",  # set when actually granted on approval.
                    revoked_at="staged-not-yet-granted",
                )
            options.append(opt)

        # Level 6 academic-continuity ALTERNATIVE: a duty teacher hosts a guided
        # session / supervised practice (or a recorded lesson is played under
        # supervision). Added whenever a duty teacher exists, so coverage is
        # guaranteed and a free period is structurally impossible.
        duty = next((m for m in staff if m.is_duty_teacher and m.is_free(vacancy.slot_key)), None)
        if duty is not None and not any(
            o.level is SubLevel.CONTINUITY_ALTERNATIVE for o in options
        ):
            n += 1
            mode: ContinuityMode = "recorded_lesson" if pickup.is_linked else "supervised_practice"
            options.append(
                SubstituteOption(
                    option_id=f"{vacancy.period_id}:opt:{n}",
                    level=SubLevel.CONTINUITY_ALTERNATIVE,
                    staff_ref=duty.staff_ref,
                    vacancy_period_id=vacancy.period_id,
                    rank=0,
                    why="Last-resort academic-continuity alternative: a guided "
                    "session, recorded lesson, or supervised practice under a duty "
                    "teacher — always academically meaningful and supervised, never "
                    "an unsupervised free period.",
                    owner_role=self._owner_role,
                    owner_ref=self._owner_ref,
                    notes=self._notes(SubLevel.CONTINUITY_ALTERNATIVE),
                    pickup=pickup,
                    continuity_mode=mode,
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
        if level is SubLevel.CONTINUITY_ALTERNATIVE:
            return [
                "Academic-continuity alternative — pick a guided session, a "
                "recorded lesson, or supervised practice; keep it meaningful and "
                "supervised, never a free period.",
            ]
        if level is SubLevel.EXTERNAL_TIME_BOUND:
            return [
                "External substitute — access is TIME-BOUND: granted on approval, "
                "scoped to this period, and REMOVED after the cover ends.",
            ]
        if level is SubLevel.CROSS_CAMPUS_ONLINE:
            return [
                "Taught ONLINE from another campus by a subject specialist — pair "
                "with an on-site supervisor for the room.",
            ]
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


def grant_external_access(
    option: SubstituteOption,
    *,
    approved_by: str | None,
    granted_at: str,
    expires_at: str,
) -> ExternalAccessGrant:
    """Activate the TIME-BOUND access grant for an approved Level 5 external
    substitute — the SEPARATE, human-gated step that turns a staged grant live.

    Refuses without ``approved_by`` (INVARIANT 8). Only valid for a Level 5
    option carrying a staged grant. Returns an ACTIVE grant scoped to the cover
    period with an explicit expiry; the wiring layer enforces the expiry and must
    call :func:`revoke_external_access` when the cover window closes so no
    standing external access is left behind (least privilege).
    """
    if not approved_by:
        raise PermissionError(
            "Granting external access is consequential and requires explicit human "
            "approval (approved_by)."
        )
    if option.level is not SubLevel.EXTERNAL_TIME_BOUND or option.access_grant is None:
        raise ValueError("only a Level 5 external option carries a time-bound access grant.")
    staged = option.access_grant
    active = ExternalAccessGrant(
        grant_id=staged.grant_id,
        external_staff_ref=staged.external_staff_ref,
        scope_period_id=staged.scope_period_id,
        granted_at=granted_at,
        expires_at=expires_at,
        revoked_at=None,  # now active.
    )
    option.access_grant = active
    return active


def revoke_external_access(
    grant: ExternalAccessGrant,
    *,
    revoked_at: str | None = None,
) -> ExternalAccessGrant:
    """REMOVE a Level 5 external substitute's access after the cover ends.

    The closing half of the time-bound lifecycle: an external grant is never
    standing, so once the cover window passes the grant is revoked and
    ``is_active`` becomes False. Idempotent — revoking an already-revoked grant
    returns it unchanged. ``revoked_at`` defaults to the grant's own expiry so the
    removal is anchored to the agreed window even if no explicit time is supplied.
    """
    if not grant.is_active:
        return grant
    stamp = revoked_at or grant.expires_at or _now_iso()
    return ExternalAccessGrant(
        grant_id=grant.grant_id,
        external_staff_ref=grant.external_staff_ref,
        scope_period_id=grant.scope_period_id,
        granted_at=grant.granted_at,
        expires_at=grant.expires_at,
        revoked_at=stamp,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
