"""The dynamic timetable + the constraint solver (B2).

The timetable is a set of scheduled periods (a section, a slot, a teacher, a
subject, a room). When a disruption happens — a teacher on leave, a room lost, a
clash introduced by an edit — the solver is asked for a *change*. It does NOT
rewrite the timetable on its own.

The solver:

  - classifies every rule it knows as **hard**, **soft**, or **contextual**
    (INVARIANT: rules are not a flat list — a hard breach disqualifies; a soft
    breach costs score; a contextual rule only applies when its condition holds);
  - generates candidate moves and SCORES them, surfacing the top *alternatives*
    with their evidence (which rules each respects or bends) and a confidence
    band;
  - NEVER commits. Producing alternatives is the whole job. Committing a change
    to a live timetable affects students, teachers, and rooms — that is a
    consequential action and sits at ``execute_with_permission`` on the
    permission ladder (INVARIANT 8). A human approves; only then is a change
    applied, and applying it is a separate, explicit call.

This mirrors the proactive Recommendation contract (A5 /
contracts/src/recommendations): every alternative carries evidence, a
confidence band, an owner, a consequence, and a "why am I seeing this" line.

Import-safe, deterministic, dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Callable, Literal, Sequence

# ---------------------------------------------------------------------------
# Slots + scheduled periods
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Slot:
    """A timetable slot: a weekday (0=Mon) and a period index within that day."""

    weekday: int  # 0 (Mon) .. 6 (Sun)
    period: int  # 1-based period number within the day

    def __post_init__(self) -> None:
        if not 0 <= self.weekday <= 6:
            raise ValueError("weekday must be 0 (Mon) .. 6 (Sun).")
        if self.period < 1:
            raise ValueError("period is 1-based.")


@dataclass(frozen=True)
class Period:
    """One scheduled period. All actors are opaque ids; labels are generic."""

    period_id: str
    section_id: str  # e.g. "Section 10-B" lives in the label store, not here.
    slot: Slot
    subject_id: str
    teacher_ref: str  # opaque canonical_uuid of the assigned teacher (no PII).
    room_id: str | None = None


# ---------------------------------------------------------------------------
# Rule classification: hard / soft / contextual
# ---------------------------------------------------------------------------


class RuleClass(str, Enum):
    """How a rule participates in scoring.

    - HARD: a breach disqualifies a candidate outright (a teacher cannot be in
      two rooms at once; a section cannot have two subjects in one slot).
    - SOFT: a breach is allowed but costs score (avoid a teacher's third
      consecutive period; keep a subject off the last slot of the day).
    - CONTEXTUAL: only applies when its condition holds for this disruption
      (e.g. "respect the substitute's subject expertise" applies only when we
      are filling a vacancy, not when we are de-clashing a room).
    """

    HARD = "hard"
    SOFT = "soft"
    CONTEXTUAL = "contextual"


@dataclass(frozen=True)
class RuleResult:
    """The outcome of evaluating one rule against a candidate."""

    rule_id: str
    rule_class: RuleClass
    satisfied: bool
    weight: float  # soft-rule penalty weight (0 for hard/contextual-not-applicable)
    detail: str  # plain-language evidence line.
    applicable: bool = True  # contextual rules can be inapplicable.


# A rule evaluates a candidate against the live timetable and returns a result,
# or ``None`` when a contextual rule does not apply to this disruption.
Rule = Callable[["Candidate", "Timetable", "Disruption"], "RuleResult | None"]


@dataclass(frozen=True)
class NamedRule:
    rule_id: str
    rule_class: RuleClass
    weight: float
    evaluate: Rule


# ---------------------------------------------------------------------------
# Disruption + candidate + scored alternative
# ---------------------------------------------------------------------------

DisruptionKind = Literal["teacher_absent", "room_lost", "clash", "manual_edit"]


@dataclass(frozen=True)
class Disruption:
    """What changed and needs resolving, without proposing the answer."""

    kind: DisruptionKind
    on_date: date
    affected_period_id: str
    # Optional context the contextual rules read.
    lost_room_id: str | None = None
    absent_teacher_ref: str | None = None


@dataclass(frozen=True)
class Candidate:
    """A proposed change to a single affected period — never applied here.

    Exactly one of the change fields is set per candidate, keeping each
    alternative atomic and explainable.
    """

    candidate_id: str
    affected_period_id: str
    new_teacher_ref: str | None = None
    new_room_id: str | None = None
    new_slot: Slot | None = None

    def describe(self) -> str:
        if self.new_teacher_ref is not None:
            return "reassign the period to a substitute teacher"
        if self.new_room_id is not None:
            return "move the period to a different room"
        if self.new_slot is not None:
            return f"shift the period to weekday {self.new_slot.weekday}, period {self.new_slot.period}"
        return "no-op"


@dataclass
class ScoredAlternative:
    """A scored, human-approvable alternative. Mirrors the A5 Recommendation
    contract: evidence, confidence, owner, consequence, why-am-I-seeing-this.

    NEVER auto-applied. ``ladder_stage`` is fixed to ``execute_with_permission``
    and ``is_consequential`` is always True — applying a timetable change
    affects people, so it waits for explicit approval (INVARIANT 8).
    """

    candidate: Candidate
    score: float  # higher is better; in [0, 1].
    rule_results: list[RuleResult]
    feasible: bool  # False when any HARD rule is breached.
    owner_role: str
    owner_ref: str
    why: str
    ladder_stage: str = "execute_with_permission"
    is_consequential: bool = True

    @property
    def confidence_band(self) -> Literal["low", "medium", "high"]:
        if not self.feasible:
            return "low"
        if self.score >= 0.8:
            return "high"
        if self.score >= 0.5:
            return "medium"
        return "low"

    @property
    def evidence(self) -> list[str]:
        """Plain-language evidence lines — which rules this respects or bends."""
        lines: list[str] = []
        for r in self.rule_results:
            if not r.applicable:
                continue
            verb = "respects" if r.satisfied else "bends"
            if r.rule_class is RuleClass.HARD and not r.satisfied:
                verb = "breaks"
            lines.append(f"{verb} [{r.rule_class.value}] {r.rule_id}: {r.detail}")
        return lines

    @property
    def consequence_of_applying(self) -> str:
        if not self.feasible:
            return (
                "Not applicable as-is: it breaks a hard rule. Applying it would "
                "create a real clash. Shown so the trade-off is visible, not to be chosen."
            )
        bent = [r for r in self.rule_results if r.applicable and not r.satisfied]
        if not bent:
            return "Applying this resolves the disruption with no soft-rule cost."
        return (
            "Applying this resolves the disruption but bends "
            f"{len(bent)} soft preference(s); see the evidence for which."
        )


# ---------------------------------------------------------------------------
# The timetable + solver
# ---------------------------------------------------------------------------


@dataclass
class Timetable:
    """A live timetable for one tenant. Read by the solver; only mutated by an
    explicit, approved :func:`apply_change` — never by the solver itself.
    """

    institution_id: str
    periods: list[Period] = field(default_factory=list)

    def by_id(self, period_id: str) -> Period | None:
        for p in self.periods:
            if p.period_id == period_id:
                return p
        return None

    def teacher_busy(self, teacher_ref: str, slot: Slot, *, ignore_period_id: str | None = None) -> bool:
        for p in self.periods:
            if p.period_id == ignore_period_id:
                continue
            if p.teacher_ref == teacher_ref and p.slot == slot:
                return True
        return False

    def room_busy(self, room_id: str, slot: Slot, *, ignore_period_id: str | None = None) -> bool:
        for p in self.periods:
            if p.period_id == ignore_period_id:
                continue
            if p.room_id is not None and p.room_id == room_id and p.slot == slot:
                return True
        return False

    def section_busy(self, section_id: str, slot: Slot, *, ignore_period_id: str | None = None) -> bool:
        for p in self.periods:
            if p.period_id == ignore_period_id:
                continue
            if p.section_id == section_id and p.slot == slot:
                return True
        return False


@dataclass
class SolverResult:
    """What the solver returns: ranked alternatives + the audit of how rules
    were classified. ``committed`` is ALWAYS False — the solver never commits."""

    disruption: Disruption
    alternatives: list[ScoredAlternative]
    committed: bool = False  # invariant: the solver never sets this True.

    @property
    def best(self) -> ScoredAlternative | None:
        feasible = [a for a in self.alternatives if a.feasible]
        return feasible[0] if feasible else None


class TimetableSolver:
    """Classifies rules, generates candidates, and scores alternatives.

    Construct with a list of :class:`NamedRule`. If none are supplied a sensible
    default set is used (the standard hard clashes plus a couple of soft and
    contextual preferences). The solver is pure: it reads the timetable and
    returns alternatives. It exposes no commit path.
    """

    def __init__(self, rules: Sequence[NamedRule] | None = None, *, owner_role: str = "coordinator") -> None:
        self._rules = list(rules) if rules is not None else default_rules()
        self._owner_role = owner_role

    @property
    def rules(self) -> list[NamedRule]:
        return list(self._rules)

    def rules_by_class(self) -> dict[RuleClass, list[str]]:
        """The classification audit: which rule sits in which class."""
        out: dict[RuleClass, list[str]] = {c: [] for c in RuleClass}
        for r in self._rules:
            out[r.rule_class].append(r.rule_id)
        return out

    def score_candidate(
        self,
        candidate: Candidate,
        timetable: Timetable,
        disruption: Disruption,
        *,
        owner_ref: str,
    ) -> ScoredAlternative:
        results: list[RuleResult] = []
        for rule in self._rules:
            res = rule.evaluate(candidate, timetable, disruption)
            if res is None:  # contextual rule that does not apply here.
                continue
            results.append(res)

        feasible = all(
            r.satisfied for r in results if r.rule_class is RuleClass.HARD and r.applicable
        )
        # Soft cost: sum of weights of breached, applicable soft rules.
        soft_total = sum(
            r.weight for r in results if r.rule_class is RuleClass.SOFT and r.applicable
        )
        soft_breached = sum(
            r.weight
            for r in results
            if r.rule_class is RuleClass.SOFT and r.applicable and not r.satisfied
        )
        # Contextual rules that apply and are satisfied add a small reward.
        ctx_applicable = [
            r for r in results if r.rule_class is RuleClass.CONTEXTUAL and r.applicable
        ]
        ctx_reward = (
            sum(1 for r in ctx_applicable if r.satisfied) / len(ctx_applicable)
            if ctx_applicable
            else 1.0
        )

        if not feasible:
            score = 0.0
        else:
            soft_score = 1.0 - (soft_breached / soft_total if soft_total else 0.0)
            # Weight the feasible score mostly on soft preferences, lightly on
            # contextual fit.
            score = round(0.8 * soft_score + 0.2 * ctx_reward, 4)

        return ScoredAlternative(
            candidate=candidate,
            score=score,
            rule_results=results,
            feasible=feasible,
            owner_role=self._owner_role,
            owner_ref=owner_ref,
            why=(
                f"A {disruption.kind} disruption on {disruption.on_date.isoformat()} "
                f"affected period {disruption.affected_period_id}; this is one scored "
                "way to resolve it, surfaced for your approval."
            ),
        )

    def solve(
        self,
        candidates: Sequence[Candidate],
        timetable: Timetable,
        disruption: Disruption,
        *,
        owner_ref: str,
        top_n: int = 3,
    ) -> SolverResult:
        """Score every candidate, rank feasible ones first by score, and return
        the top ``top_n`` alternatives. NEVER commits.
        """
        scored = [
            self.score_candidate(c, timetable, disruption, owner_ref=owner_ref)
            for c in candidates
        ]
        # Feasible first; within each group, higher score first; stable by id.
        scored.sort(key=lambda a: (not a.feasible, -a.score, a.candidate.candidate_id))
        return SolverResult(disruption=disruption, alternatives=scored[: max(0, top_n)])


def apply_change(
    timetable: Timetable,
    alternative: ScoredAlternative,
    *,
    approved_by: str | None,
) -> Period:
    """Apply an approved alternative to the live timetable — the SEPARATE,
    explicit, human-gated step.

    Refuses without an ``approved_by`` (an opaque human ref): a timetable change
    is consequential and never auto-fires (INVARIANT 8). Refuses an infeasible
    alternative outright. The solver never calls this; only an approval workflow
    does, after a human decision.
    """
    if not approved_by:
        raise PermissionError(
            "A timetable change is consequential and requires explicit human "
            "approval (approved_by). The solver never commits on its own."
        )
    if not alternative.feasible:
        raise ValueError("cannot apply an infeasible alternative (it breaks a hard rule).")

    old = timetable.by_id(alternative.candidate.affected_period_id)
    if old is None:
        raise ValueError("affected period is not in this timetable.")

    cand = alternative.candidate
    updated = Period(
        period_id=old.period_id,
        section_id=old.section_id,
        slot=cand.new_slot or old.slot,
        subject_id=old.subject_id,
        teacher_ref=cand.new_teacher_ref or old.teacher_ref,
        room_id=cand.new_room_id if cand.new_room_id is not None else old.room_id,
    )
    timetable.periods = [updated if p.period_id == old.period_id else p for p in timetable.periods]
    return updated


# ---------------------------------------------------------------------------
# Default rule set
# ---------------------------------------------------------------------------


def _effective_slot(candidate: Candidate, timetable: Timetable) -> Slot | None:
    period = timetable.by_id(candidate.affected_period_id)
    if period is None:
        return None
    return candidate.new_slot or period.slot


def default_rules() -> list[NamedRule]:
    """The standard rule set, explicitly classified hard/soft/contextual."""

    def no_teacher_clash(c: Candidate, tt: Timetable, d: Disruption) -> RuleResult | None:
        period = tt.by_id(c.affected_period_id)
        slot = _effective_slot(c, tt)
        if period is None or slot is None:
            return None
        teacher = c.new_teacher_ref or period.teacher_ref
        clash = tt.teacher_busy(teacher, slot, ignore_period_id=period.period_id)
        return RuleResult(
            rule_id="no_teacher_double_booking",
            rule_class=RuleClass.HARD,
            satisfied=not clash,
            weight=0.0,
            detail="the assigned teacher is free in this slot"
            if not clash
            else "the assigned teacher is already teaching another section then",
        )

    def no_room_clash(c: Candidate, tt: Timetable, d: Disruption) -> RuleResult | None:
        period = tt.by_id(c.affected_period_id)
        slot = _effective_slot(c, tt)
        if period is None or slot is None:
            return None
        room = c.new_room_id if c.new_room_id is not None else period.room_id
        if room is None:
            return RuleResult(
                rule_id="no_room_double_booking",
                rule_class=RuleClass.HARD,
                satisfied=True,
                weight=0.0,
                detail="no room assigned, nothing to clash",
            )
        clash = tt.room_busy(room, slot, ignore_period_id=period.period_id)
        return RuleResult(
            rule_id="no_room_double_booking",
            rule_class=RuleClass.HARD,
            satisfied=not clash,
            weight=0.0,
            detail="the room is free in this slot"
            if not clash
            else "the room is already occupied then",
        )

    def no_section_clash(c: Candidate, tt: Timetable, d: Disruption) -> RuleResult | None:
        period = tt.by_id(c.affected_period_id)
        slot = _effective_slot(c, tt)
        if period is None or slot is None:
            return None
        # Only meaningful when we shift the slot; a same-slot fill cannot clash
        # the section with itself.
        if c.new_slot is None:
            return RuleResult(
                rule_id="no_section_double_booking",
                rule_class=RuleClass.HARD,
                satisfied=True,
                weight=0.0,
                detail="slot unchanged; the section is not moved into a clash",
            )
        clash = tt.section_busy(period.section_id, slot, ignore_period_id=period.period_id)
        return RuleResult(
            rule_id="no_section_double_booking",
            rule_class=RuleClass.HARD,
            satisfied=not clash,
            weight=0.0,
            detail="the section is free in the target slot"
            if not clash
            else "the section already has a period in the target slot",
        )

    def avoid_overload(c: Candidate, tt: Timetable, d: Disruption) -> RuleResult | None:
        period = tt.by_id(c.affected_period_id)
        if period is None:
            return None
        teacher = c.new_teacher_ref or period.teacher_ref
        load = sum(1 for p in tt.periods if p.teacher_ref == teacher and p.period_id != period.period_id)
        # Soft: prefer teachers under a daily-ish load of 6 across the visible set.
        ok = load < 6
        return RuleResult(
            rule_id="avoid_teacher_overload",
            rule_class=RuleClass.SOFT,
            satisfied=ok,
            weight=1.0,
            detail=f"teacher carries {load} other period(s); under the preferred ceiling"
            if ok
            else f"teacher already carries {load} period(s); this adds load",
        )

    def keep_room_stable(c: Candidate, tt: Timetable, d: Disruption) -> RuleResult | None:
        period = tt.by_id(c.affected_period_id)
        if period is None:
            return None
        moved = c.new_room_id is not None and c.new_room_id != period.room_id
        return RuleResult(
            rule_id="prefer_room_stability",
            rule_class=RuleClass.SOFT,
            satisfied=not moved,
            weight=0.5,
            detail="keeps the section in its usual room"
            if not moved
            else "moves the section to a different room",
        )

    def substitute_subject_fit(c: Candidate, tt: Timetable, d: Disruption) -> RuleResult | None:
        # CONTEXTUAL: only applies when we are filling a teacher vacancy.
        if d.kind != "teacher_absent" or c.new_teacher_ref is None:
            return None  # inapplicable -> not scored.
        # Without a teacher-subject competency feed we cannot confirm expertise;
        # we mark it applicable-but-unconfirmed (satisfied=False, low weight) so
        # the human sees expertise is unverified rather than silently assumed.
        return RuleResult(
            rule_id="substitute_subject_expertise",
            rule_class=RuleClass.CONTEXTUAL,
            satisfied=False,
            weight=0.0,
            detail="subject-expertise of the proposed substitute is unverified "
            "(no competency feed wired); confirm before approving",
            applicable=True,
        )

    return [
        NamedRule("no_teacher_double_booking", RuleClass.HARD, 0.0, no_teacher_clash),
        NamedRule("no_room_double_booking", RuleClass.HARD, 0.0, no_room_clash),
        NamedRule("no_section_double_booking", RuleClass.HARD, 0.0, no_section_clash),
        NamedRule("avoid_teacher_overload", RuleClass.SOFT, 1.0, avoid_overload),
        NamedRule("prefer_room_stability", RuleClass.SOFT, 0.5, keep_room_stable),
        NamedRule("substitute_subject_expertise", RuleClass.CONTEXTUAL, 0.0, substitute_subject_fit),
    ]
