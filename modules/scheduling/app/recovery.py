"""Pacing RECOVERY + period SWAPPING + low-risk automation within policy (B2).

:mod:`app.pacing` detects DRIFT — it tells a coordinator a section+subject is
slipping, behind, or at risk, with evidence, an owner, and the consequence of
ignoring it. It deliberately stops there: pacing never reschedules on its own.

This module is the next move. Given a drifting pacing finding it RECOMMENDS the
recovery actions the document names (line: *"when a subject falls behind it
recommends recovery — added periods, revision blocks, reallocated slots"*):

  - ADD_PERIOD       — schedule an extra period of the subject to claw back the
                       owed periods;
  - REVISION_BLOCK   — a consolidation/revision block before an assessment when
                       drift compressed the run-up;
  - REALLOCATE_SLOT  — move a slot from an ahead-of-pace subject to the behind
                       one (the week's total teaching time is conserved);
  - PERIOD_SWAP      — exchange two periods ACROSS THE WEEK so the subject lands
                       on a better day without adding or removing any teaching
                       time (a pure rearrangement).

Every recommendation mirrors the A5 Recommendation contract: evidence, a
confidence band, an owner, a consequence, and a why-am-I-seeing-this line.

The PERMISSION LADDER is the spine of this module (INVARIANT 8). A recovery
action is consequential — it changes what students and teachers do on a given
day — so by default it is **prepared, not fired**: each recommendation carries
``ladder_stage = "execute_with_permission"`` and waits for a human.

The one carefully bounded exception is the document's own
*"low-risk changes can be [applied] within policy"* (line 515) / *"the engine
handles low-risk ones within policy"* (line 680). A change qualifies for the
LOW-RISK-AUTOMATION path ONLY when an explicit :class:`AutomationPolicy` says so
AND the action clears every one of the policy's bounds (it is a pure same-week
rearrangement, it introduces no hard clash, it stays under a daily-load ceiling,
and it is not inside an exam blackout). Anything consequential beyond that — and
ALL of add-period / revision-block / reallocate-slot, which change total teaching
time — can never be auto-applied; they always return ``requires_approval``.

Pure, deterministic, dependency-free. Opaque ids + generic labels only; no PII.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Literal, Sequence

from .pacing import PacingStatus
from .timetable import Period, Slot, Timetable


# ---------------------------------------------------------------------------
# Recovery action kinds
# ---------------------------------------------------------------------------


class RecoveryKind(str, Enum):
    """The recovery actions the document names for a behind syllabus."""

    ADD_PERIOD = "add_period"  # extra period of the subject.
    REVISION_BLOCK = "revision_block"  # consolidation block before assessment.
    REALLOCATE_SLOT = "reallocate_slot"  # take a slot from an ahead subject.
    PERIOD_SWAP = "period_swap"  # exchange two periods across the week.


RECOVERY_LABELS: dict[RecoveryKind, str] = {
    RecoveryKind.ADD_PERIOD: "Add an extra period of the subject",
    RecoveryKind.REVISION_BLOCK: "Insert a revision / consolidation block",
    RecoveryKind.REALLOCATE_SLOT: "Reallocate a slot from an ahead-of-pace subject",
    RecoveryKind.PERIOD_SWAP: "Swap two periods across the week",
}

# Whether the action changes the week's total teaching minutes for the subject.
# add/revision/reallocate add subject time; a swap is time-neutral (pure move).
_CHANGES_TOTAL_TIME: dict[RecoveryKind, bool] = {
    RecoveryKind.ADD_PERIOD: True,
    RecoveryKind.REVISION_BLOCK: True,
    RecoveryKind.REALLOCATE_SLOT: True,
    RecoveryKind.PERIOD_SWAP: False,
}


# ---------------------------------------------------------------------------
# A recommended recovery action (prepared, never auto-fired by default)
# ---------------------------------------------------------------------------


@dataclass
class RecoveryAction:
    """One recommended recovery action for a drifting section+subject.

    NEVER auto-applied by default. ``ladder_stage`` is
    ``execute_with_permission`` and ``is_consequential`` is True — applying it
    changes the live timetable, so it waits for a human (INVARIANT 8). The only
    path to auto-application is :func:`evaluate_low_risk`, which a caller invokes
    explicitly with a policy and which still refuses anything outside the policy
    bounds.
    """

    action_id: str
    kind: RecoveryKind
    section_id: str
    subject_id: str
    # The period being created/moved (the recommendation, not a committed write).
    target_slot: Slot | None = None
    # For a swap / reallocation: the period whose slot we exchange or borrow.
    swap_with_period_id: str | None = None
    donor_subject_id: str | None = None  # for reallocate: the ahead subject.
    owed_periods: float = 0.0  # how far behind the subject is.
    owner_role: str = "coordinator"
    owner_ref: str = ""
    ladder_stage: str = "execute_with_permission"
    is_consequential: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return RECOVERY_LABELS[self.kind]

    @property
    def changes_total_teaching_time(self) -> bool:
        return _CHANGES_TOTAL_TIME[self.kind]

    @property
    def is_time_neutral(self) -> bool:
        """A pure rearrangement that adds/removes no teaching time (a swap)."""
        return not self.changes_total_teaching_time

    @property
    def confidence_band(self) -> Literal["low", "medium", "high"]:
        # A time-neutral swap is the lowest-risk, most-confident move; actions
        # that change total time are higher-stakes, so medium.
        return "high" if self.is_time_neutral else "medium"

    @property
    def why(self) -> str:
        return (
            f"{self.label} for {self.subject_id} in {self.section_id}: the subject "
            f"is behind by ~{self.owed_periods:.1f} period(s). Surfaced as a "
            "recommendation for your approval; recovery never auto-reschedules "
            "unless an explicit low-risk policy permits it."
        )

    @property
    def consequence_of_applying(self) -> str:
        if self.changes_total_teaching_time:
            return (
                "Applying this adds teaching time for the subject and shifts the "
                "week's balance; a human approves before it touches the timetable."
            )
        return (
            "Applying this rearranges existing periods within the week (no time "
            "added or removed); low-risk, but still applied under policy."
        )


# ---------------------------------------------------------------------------
# Recommending recovery from a drift finding
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecoveryContext:
    """Inputs a recommender needs beyond the drift finding.

    ``free_slots`` are slots the section is free in (candidate homes for an added
    period or revision block). ``ahead_subjects`` lists subject_ids that are
    ahead of pace (donor candidates for a reallocation). ``assessment_near`` ==
    True biases toward a revision block. All ids opaque; no PII.
    """

    free_slots: list[Slot] = field(default_factory=list)
    ahead_subjects: list[str] = field(default_factory=list)
    assessment_near: bool = False


def recommend_recovery(
    status: PacingStatus,
    context: RecoveryContext | None = None,
    *,
    owner_ref: str = "",
    owner_role: str = "coordinator",
) -> list[RecoveryAction]:
    """Recommend recovery actions for a drifting pacing finding.

    Returns an empty list when the section is on track or ahead — there is
    nothing to recover. When it is drifting, builds the applicable actions from
    the named menu (add period, revision block, reallocate slot) ordered most-
    helpful first. NEVER applies anything; these are recommendations only.
    """
    if not status.is_drifting:
        return []
    ctx = context or RecoveryContext()
    owed = max(0.0, status.drift_periods)
    actions: list[RecoveryAction] = []
    n = 0

    # A revision block is offered first when an assessment is near AND the
    # section is at least "behind" — that is exactly when compressed run-up hurts.
    if ctx.assessment_near and status.band in ("behind", "at_risk"):
        n += 1
        slot = ctx.free_slots[0] if ctx.free_slots else None
        actions.append(
            RecoveryAction(
                action_id=f"rec:{status.section_id}:{status.subject_id}:{n}",
                kind=RecoveryKind.REVISION_BLOCK,
                section_id=status.section_id,
                subject_id=status.subject_id,
                target_slot=slot,
                owed_periods=owed,
                owner_ref=owner_ref,
                owner_role=owner_role,
                notes=[
                    "An assessment is near and the subject is behind; consolidate "
                    "before testing rather than rushing new material.",
                ],
            )
        )

    # Add an extra period whenever there is a free slot to put it in.
    if ctx.free_slots:
        n += 1
        actions.append(
            RecoveryAction(
                action_id=f"rec:{status.section_id}:{status.subject_id}:{n}",
                kind=RecoveryKind.ADD_PERIOD,
                section_id=status.section_id,
                subject_id=status.subject_id,
                target_slot=ctx.free_slots[0],
                owed_periods=owed,
                owner_ref=owner_ref,
                owner_role=owner_role,
                notes=["Claws back owed periods directly; check teacher load first."],
            )
        )

    # Reallocate a slot FROM an ahead-of-pace subject (time conserved overall).
    if ctx.ahead_subjects:
        n += 1
        actions.append(
            RecoveryAction(
                action_id=f"rec:{status.section_id}:{status.subject_id}:{n}",
                kind=RecoveryKind.REALLOCATE_SLOT,
                section_id=status.section_id,
                subject_id=status.subject_id,
                donor_subject_id=ctx.ahead_subjects[0],
                owed_periods=owed,
                owner_ref=owner_ref,
                owner_role=owner_role,
                notes=[
                    f"Borrow a slot from {ctx.ahead_subjects[0]} (ahead of pace) "
                    "so the week's total teaching time is unchanged.",
                ],
            )
        )

    return actions


# ---------------------------------------------------------------------------
# Period SWAPPING across the week
# ---------------------------------------------------------------------------


@dataclass
class PeriodSwap:
    """A proposed exchange of the slots of two existing periods across the week.

    A swap adds and removes nothing — it is a pure rearrangement, which is what
    makes it the lowest-risk recovery move and the only family eligible for the
    low-risk-automation path. Both periods keep everything except their slot,
    which they trade. NEVER applied here; :func:`apply_swap` is the separate,
    gated step.
    """

    swap_id: str
    period_a_id: str
    period_b_id: str
    owner_role: str = "coordinator"
    owner_ref: str = ""
    ladder_stage: str = "execute_with_permission"
    is_consequential: bool = True

    @property
    def why(self) -> str:
        return (
            f"Swap the slots of periods {self.period_a_id} and {self.period_b_id} "
            "to place the subject on a better day. Time-neutral; surfaced for "
            "approval (or low-risk auto-apply under policy)."
        )


def propose_period_swap(
    timetable: Timetable,
    period_a_id: str,
    period_b_id: str,
    *,
    owner_ref: str = "",
    owner_role: str = "coordinator",
) -> PeriodSwap:
    """Propose swapping the slots of two existing periods. Validates only that
    both periods exist; does NOT apply the swap and does NOT check clashes here —
    feasibility is checked at apply / low-risk-evaluation time so the proposal is
    cheap to surface. Refuses a self-swap (nothing to do)."""
    if period_a_id == period_b_id:
        raise ValueError("cannot swap a period with itself.")
    if timetable.by_id(period_a_id) is None or timetable.by_id(period_b_id) is None:
        raise ValueError("both periods must exist in this timetable to swap.")
    return PeriodSwap(
        swap_id=f"swap:{period_a_id}:{period_b_id}",
        period_a_id=period_a_id,
        period_b_id=period_b_id,
        owner_ref=owner_ref,
        owner_role=owner_role,
    )


def _swap_is_feasible(timetable: Timetable, swap: PeriodSwap) -> tuple[bool, list[str]]:
    """Would swapping the two periods' slots introduce any hard clash?

    Returns (feasible, reasons). A swap is feasible when, after the exchange,
    neither period's teacher, section, or room is double-booked. Same-slot swaps
    are trivially feasible. Pure read; never mutates the timetable.
    """
    a = timetable.by_id(swap.period_a_id)
    b = timetable.by_id(swap.period_b_id)
    if a is None or b is None:
        return False, ["one or both periods no longer exist in the timetable"]
    if a.slot == b.slot:
        return True, []

    reasons: list[str] = []
    # Check each moved period against everything EXCEPT the two being swapped.
    others = [p for p in timetable.periods if p.period_id not in (a.period_id, b.period_id)]
    for moved, target_slot in ((a, b.slot), (b, a.slot)):
        for other in others:
            if other.slot != target_slot:
                continue
            if other.teacher_ref == moved.teacher_ref:
                reasons.append(f"teacher clash for period {moved.period_id} in the target slot")
            if other.section_id == moved.section_id:
                reasons.append(f"section clash for period {moved.period_id} in the target slot")
            if (
                moved.room_id is not None
                and other.room_id is not None
                and other.room_id == moved.room_id
            ):
                reasons.append(f"room clash for period {moved.period_id} in the target slot")
    return (not reasons), reasons


def apply_swap(
    timetable: Timetable,
    swap: PeriodSwap,
    *,
    approved_by: str | None,
) -> tuple[Period, Period]:
    """Apply an approved period swap — the SEPARATE, explicit, human-gated step.

    Refuses without ``approved_by`` (INVARIANT 8) and refuses an infeasible swap
    (one that would create a hard clash). Exchanges only the two periods' slots,
    leaving every other field intact, and returns the two updated periods. The
    recommender never calls this; an approval workflow (or the low-risk path,
    which supplies its own ``approved_by`` token) does.
    """
    if not approved_by:
        raise PermissionError(
            "A period swap is consequential and requires explicit human approval "
            "(approved_by). Proposals never apply themselves."
        )
    feasible, reasons = _swap_is_feasible(timetable, swap)
    if not feasible:
        raise ValueError(f"cannot apply an infeasible swap: {'; '.join(reasons)}")

    a = timetable.by_id(swap.period_a_id)
    b = timetable.by_id(swap.period_b_id)
    assert a is not None and b is not None  # feasibility check already guaranteed.
    new_a = Period(a.period_id, a.section_id, b.slot, a.subject_id, a.teacher_ref, a.room_id)
    new_b = Period(b.period_id, b.section_id, a.slot, b.subject_id, b.teacher_ref, b.room_id)
    timetable.periods = [
        new_a if p.period_id == a.period_id else (new_b if p.period_id == b.period_id else p)
        for p in timetable.periods
    ]
    return new_a, new_b


# ---------------------------------------------------------------------------
# Low-risk automation WITHIN POLICY
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AutomationPolicy:
    """The bounds within which a low-risk change MAY be auto-applied.

    The document permits *"low-risk changes ... within policy"*. This makes the
    policy explicit and conservative: automation is OFF unless ``enabled`` is set,
    only TIME-NEUTRAL swaps are ever eligible (never anything that changes total
    teaching time), the swap must stay inside the same week, it must add no hard
    clash, it must keep every teacher under ``max_teacher_periods_per_day``, and
    it must avoid any slot inside an exam blackout. Missing or disabled policy =>
    nothing is auto-applied.
    """

    enabled: bool = False
    max_teacher_periods_per_day: int = 6
    same_week_only: bool = True
    exam_blackout_slots: frozenset[tuple[int, int]] = frozenset()  # (weekday, period).

    def _slot_in_blackout(self, slot: Slot) -> bool:
        return (slot.weekday, slot.period) in self.exam_blackout_slots


@dataclass
class LowRiskDecision:
    """The outcome of evaluating whether a change clears the low-risk policy.

    ``auto_apply`` is True ONLY when policy is enabled and every bound is met;
    otherwise ``requires_approval`` is True and ``reasons`` explains why it could
    not be automated. This is the structural realisation of the permission ladder:
    consequential-by-default, auto only inside an explicit, audited envelope.
    """

    auto_apply: bool
    requires_approval: bool
    reasons: list[str] = field(default_factory=list)
    ladder_stage: str = "execute_with_permission"

    def __post_init__(self) -> None:
        # The two flags are mutually exclusive by construction.
        if self.auto_apply == self.requires_approval:
            raise ValueError("a decision is exactly one of auto_apply / requires_approval.")
        if self.auto_apply:
            self.ladder_stage = "auto_within_policy"


def _teacher_day_load_after_swap(timetable: Timetable, swap: PeriodSwap) -> dict[tuple[str, int], int]:
    a = timetable.by_id(swap.period_a_id)
    b = timetable.by_id(swap.period_b_id)
    assert a is not None and b is not None
    load: dict[tuple[str, int], int] = {}
    for p in timetable.periods:
        slot = p.slot
        if p.period_id == a.period_id:
            slot = b.slot
        elif p.period_id == b.period_id:
            slot = a.slot
        key = (p.teacher_ref, slot.weekday)
        load[key] = load.get(key, 0) + 1
    return load


def evaluate_low_risk(
    timetable: Timetable,
    swap: PeriodSwap,
    policy: AutomationPolicy,
) -> LowRiskDecision:
    """Decide whether a period SWAP qualifies for low-risk auto-application.

    Only swaps are ever considered (they are time-neutral). The decision is
    ``requires_approval`` unless EVERY bound holds: policy enabled; the swap is
    feasible (no hard clash); both target slots are in the same week (a swap is
    same-week by nature, asserted explicitly); no target slot is in an exam
    blackout; and no teacher exceeds the daily ceiling after the swap. Any
    failure returns ``requires_approval`` with reasons — never a silent auto-fire.
    """
    reasons: list[str] = []
    if not policy.enabled:
        reasons.append("automation policy is disabled; all changes require approval")
        return LowRiskDecision(auto_apply=False, requires_approval=True, reasons=reasons)

    a = timetable.by_id(swap.period_a_id)
    b = timetable.by_id(swap.period_b_id)
    if a is None or b is None:
        return LowRiskDecision(
            auto_apply=False,
            requires_approval=True,
            reasons=["one or both periods are not in the timetable"],
        )

    feasible, clash_reasons = _swap_is_feasible(timetable, swap)
    if not feasible:
        reasons.extend(clash_reasons)

    if policy.same_week_only and (a.slot.weekday > 6 or b.slot.weekday > 6):  # defensive.
        reasons.append("swap crosses outside the working week")

    if policy._slot_in_blackout(a.slot) or policy._slot_in_blackout(b.slot):
        reasons.append("a target slot falls inside an exam blackout")

    load = _teacher_day_load_after_swap(timetable, swap)
    over = [k for k, v in load.items() if v > policy.max_teacher_periods_per_day]
    if over:
        reasons.append(
            f"{len(over)} teacher-day(s) would exceed the {policy.max_teacher_periods_per_day}-period ceiling"
        )

    if reasons:
        return LowRiskDecision(auto_apply=False, requires_approval=True, reasons=reasons)
    return LowRiskDecision(auto_apply=True, requires_approval=False)


def auto_apply_low_risk(
    timetable: Timetable,
    swap: PeriodSwap,
    policy: AutomationPolicy,
    *,
    automation_actor: str = "scheduling-engine:low-risk-policy",
) -> tuple[Period, Period]:
    """Apply a swap on the low-risk-automation path — only if policy permits.

    This is the ONLY function in the module that may apply a change without a
    human in the loop, and it does so strictly inside the policy envelope: it
    re-runs :func:`evaluate_low_risk` and refuses (``PermissionError``) unless the
    decision is ``auto_apply``. The audited ``automation_actor`` is recorded as
    the approver so the action is still traceable — automation is accountable,
    not anonymous. Everything outside the envelope must go through human approval.
    """
    decision = evaluate_low_risk(timetable, swap, policy)
    if not decision.auto_apply:
        raise PermissionError(
            "this change does not qualify for low-risk auto-application: "
            + "; ".join(decision.reasons)
            + ". It requires explicit human approval."
        )
    # Inside the envelope: apply, recording the policy actor as the approver.
    return apply_swap(timetable, swap, approved_by=automation_actor)
