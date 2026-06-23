"""Adaptive lesson & course planning (d6).

The teacher starts from "what am I teaching today," and the platform prepares
the plan against curriculum requirements and prior performance. Plans are built
at four scopes — annual, unit, weekly, daily — and every plan item is MAPPED TO
THE ONTOLOGY by opaque outcome ids (the board-agnostic academic graph the spine
owns; this module never hard-codes a board, INVARIANT-adjacent).

The keystone behaviour: the next plan AUTOMATICALLY ADAPTS to the previous
plan's completion and how students performed on those outcomes. Adaptation is
computed from prior performance readings produced by the intelligence engine
(spine) — we CONSUME those readings, we never author mastery here.

Human authority (INVARIANT 8 / principle 3): a plan is PREPARED as a DRAFT,
never auto-published. Adaptation forks a NEW draft plan; it never mutates the
base plan in place (events are append-only; a plan's history is a chain of
versions).

Pure, deterministic, dependency-free: same inputs (plan + prior performance) ->
same adapted plan. No network, no DB, no provider.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Callable, Iterable, List, Optional, Sequence

from .events import EventLog, EventType


# ---------------------------------------------------------------------------
# Scope — annual / unit / weekly / daily hierarchy
# ---------------------------------------------------------------------------


class PlanScope(str, Enum):
    """The grain of a plan. The order encodes the hierarchy: a coarser scope may
    parent a finer one (annual -> unit -> weekly -> daily), never the reverse."""

    ANNUAL = "annual"
    UNIT = "unit"
    WEEKLY = "weekly"
    DAILY = "daily"

    @property
    def rank(self) -> int:
        return _SCOPE_ORDER.index(self)


_SCOPE_ORDER: tuple[PlanScope, ...] = (
    PlanScope.ANNUAL,
    PlanScope.UNIT,
    PlanScope.WEEKLY,
    PlanScope.DAILY,
)


# ---------------------------------------------------------------------------
# Ontology mapping — every plan item points at outcome ids by opaque token
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutcomeRef:
    """An opaque pointer into the academic graph. The plan item is ABOUT these
    outcomes; the engine and the diary reconcile against the same ids. No name,
    no board — an opaque token only (INVARIANT 1 + 2)."""

    outcome_id: str

    def __post_init__(self) -> None:
        if not self.outcome_id:
            raise ValueError("OutcomeRef.outcome_id is required (opaque ontology token).")


@dataclass
class PlanItem:
    """One teachable unit of a plan, mapped to the ontology.

    ``outcomes`` are the opaque outcome refs the item teaches. An item with no
    outcomes is UNMAPPED — flagged, never silently accepted. The adaptation flags
    (``rolled_over_from``, ``reinforcement``, ``compressed``) make every change
    auditable so the diary and a coordinator can read why the next plan looks the
    way it does (principle 2, explainability).
    """

    item_id: str
    title: str
    outcomes: List[OutcomeRef] = field(default_factory=list)
    estimated_minutes: int = 40
    priority: int = 0
    rolled_over_from: Optional[str] = None
    reinforcement: bool = False
    compressed: bool = False

    def __post_init__(self) -> None:
        if not self.item_id:
            raise ValueError("PlanItem.item_id is required.")
        if self.estimated_minutes < 0:
            raise ValueError("PlanItem.estimated_minutes must be non-negative.")
        # Normalise outcome refs (accept bare strings as a convenience).
        norm: List[OutcomeRef] = []
        for o in self.outcomes:
            norm.append(o if isinstance(o, OutcomeRef) else OutcomeRef(outcome_id=str(o)))
        self.outcomes = norm

    @property
    def outcome_ids(self) -> tuple[str, ...]:
        return tuple(o.outcome_id for o in self.outcomes)

    @property
    def is_mapped(self) -> bool:
        return bool(self.outcomes)


@dataclass
class Plan:
    """A plan at one scope for one owner+subject, mapped to the ontology.

    A plan may parent finer-scoped child plans (annual -> unit -> ...). Ontology
    coverage rolls up across children so a coarse plan's mapped outcomes include
    everything its children teach.
    """

    plan_id: str
    scope: PlanScope
    owner_uuid: str
    subject_uuid: str
    items: List[PlanItem] = field(default_factory=list)
    children: List["Plan"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.plan_id:
            raise ValueError("Plan.plan_id is required.")
        self.items = list(self.items)
        self.children = list(self.children)

    # -- hierarchy ---------------------------------------------------------

    def add_child(self, child: "Plan") -> "Plan":
        """Attach a finer-scoped child plan. A plan may only parent a STRICTLY
        finer scope (annual parents unit, never the reverse) — the hierarchy is
        load-bearing."""
        if not isinstance(child, Plan):
            raise TypeError("Plan.add_child requires a Plan.")
        if child.scope.rank <= self.scope.rank:
            raise ValueError(
                f"a {self.scope.value} plan cannot parent a {child.scope.value} "
                "plan; children must be a strictly finer scope."
            )
        self.children.append(child)
        return child

    # -- ontology coverage -------------------------------------------------

    def mapped_outcome_ids(self) -> tuple[str, ...]:
        """Every outcome id this plan (and its children) maps to, deduped, in
        order."""
        seen: List[str] = []
        for it in self.items:
            for oid in it.outcome_ids:
                if oid not in seen:
                    seen.append(oid)
        for child in self.children:
            for oid in child.mapped_outcome_ids():
                if oid not in seen:
                    seen.append(oid)
        return tuple(seen)

    def unmapped_items(self) -> tuple[PlanItem, ...]:
        """Items (this plan + children) with no ontology mapping — the gaps a
        coordinator must close before the plan is honest."""
        gaps: List[PlanItem] = [it for it in self.items if not it.is_mapped]
        for child in self.children:
            gaps.extend(child.unmapped_items())
        return tuple(gaps)

    def is_fully_mapped(self) -> bool:
        """True when every item (this plan + children) maps to at least one
        ontology outcome."""
        return not self.unmapped_items()

    def covers_outcome(self, outcome_id: str) -> bool:
        return outcome_id in self.mapped_outcome_ids()

    @property
    def total_estimated_minutes(self) -> int:
        return sum(it.estimated_minutes for it in self.items)


# ---------------------------------------------------------------------------
# Prior performance — the consumed signal that drives adaptation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PriorPerformance:
    """The prior reading for one outcome, CONSUMED from the intelligence layer
    and the delivery surface.

    ``completed`` is whether the planned item was actually delivered;
    ``mastery`` is the cohort's mastery on the outcome in [0,1]; ``item_id``
    links the reading back to the plan item it came from."""

    outcome_id: str
    completed: bool
    mastery: float
    item_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.outcome_id:
            raise ValueError("PriorPerformance.outcome_id is required (opaque token).")
        if not 0.0 <= self.mastery <= 1.0:
            raise ValueError("mastery must be in [0,1].")


# ---------------------------------------------------------------------------
# Generation + adaptation
# ---------------------------------------------------------------------------


class PlanGenerator:
    """Builds DRAFT plans and adapts them to prior performance.

    Tunables:
      * ``resolve_outcome`` — an injected predicate that checks whether an
        outcome ref resolves in the ontology snapshot. Unresolved refs are
        flagged on the drafted event (evidence over assertion) but never silently
        dropped.
      * ``reinforce_below`` — outcomes whose mastery is below this get a
        REINFORCEMENT item in the next plan.
      * ``compress_above`` — outcomes whose mastery is above this are COMPRESSED
        (less time) in the next plan.
      * ``event_log`` — optional append-only log for drafted/adapted events.
    """

    def __init__(
        self,
        resolve_outcome: Optional[Callable[[OutcomeRef], bool]] = None,
        event_log: Optional[EventLog] = None,
        reinforce_below: float = 0.6,
        compress_above: float = 0.9,
        rollover_priority: int = 1,
        compress_factor: float = 0.5,
    ) -> None:
        self._resolve = resolve_outcome
        self._events = event_log
        self.reinforce_below = reinforce_below
        self.compress_above = compress_above
        self.rollover_priority = rollover_priority
        self.compress_factor = compress_factor

    # -- draft -------------------------------------------------------------

    def draft(
        self,
        plan_id: str,
        scope: PlanScope,
        owner_uuid: str,
        subject_uuid: str,
        items: Sequence[PlanItem],
    ) -> Plan:
        """Draft a plan from the supplied items. Generation never approves
        (principle 3 / INVARIANT 8); the plan is a DRAFT a human reviews.

        If an outcome resolver is configured, any item outcome that does not
        resolve in the ontology is recorded on the drafted event so the gap is
        auditable — never silently accepted."""
        plan = Plan(
            plan_id=plan_id,
            scope=scope,
            owner_uuid=owner_uuid,
            subject_uuid=subject_uuid,
            items=[copy.deepcopy(it) for it in items],
        )

        unresolved: List[str] = []
        if self._resolve is not None:
            for it in plan.items:
                for ref in it.outcomes:
                    if not self._resolve(ref) and ref.outcome_id not in unresolved:
                        unresolved.append(ref.outcome_id)

        if self._events is not None:
            self._events.emit(
                EventType.PLAN_DRAFTED,
                subject_uuid=subject_uuid,
                payload={
                    "plan_id": plan_id,
                    "scope": scope.value,
                    "item_count": len(plan.items),
                    "fully_mapped": plan.is_fully_mapped(),
                    "unresolved_outcomes": unresolved,
                },
            )
        return plan

    # -- adapt -------------------------------------------------------------

    def adapt(
        self,
        base: Plan,
        prior: Iterable[PriorPerformance],
        new_plan_id: str,
    ) -> Plan:
        """Produce the NEXT plan from a base plan + prior performance.

        Rules:
          1. A planned item that was NOT completed is ROLLED OVER (prioritised)
             into the next plan — unfinished business comes first.
          2. A delivered outcome whose mastery is below ``reinforce_below`` gets
             a REINFORCEMENT item — re-teach before racing on.
          3. A delivered outcome whose mastery is above ``compress_above`` is
             COMPRESSED (its item carried forward with reduced time).

        The base plan is NEVER mutated (events are append-only). The result is a
        fresh DRAFT plan a human reviews.
        """
        prior_readings = list(prior)
        prior_by_item: dict[str, PriorPerformance] = {
            p.item_id: p for p in prior_readings if p.item_id is not None
        }
        prior_by_outcome: dict[str, PriorPerformance] = {}
        for p in prior_readings:
            prior_by_outcome.setdefault(p.outcome_id, p)

        new_items: List[PlanItem] = []
        rolled = 0
        reinforcements = 0
        compressed = 0

        for it in base.items:
            perf = prior_by_item.get(it.item_id)
            if perf is None:
                # Fall back to the first matching outcome reading.
                for oid in it.outcome_ids:
                    if oid in prior_by_outcome:
                        perf = prior_by_outcome[oid]
                        break

            if perf is None:
                new_items.append(copy.deepcopy(it))
                continue

            if not perf.completed:
                # Rule 1: roll the unfinished item forward, prioritised.
                rolled_item = copy.deepcopy(it)
                rolled_item.rolled_over_from = it.item_id
                rolled_item.priority = max(it.priority, 0) + self.rollover_priority
                new_items.append(rolled_item)
                rolled += 1
                continue

            # Delivered. Decide compress / reinforce / carry.
            if perf.mastery >= self.compress_above:
                # Rule 3: compress a strongly-mastered item.
                comp = copy.deepcopy(it)
                comp.compressed = True
                comp.estimated_minutes = int(it.estimated_minutes * self.compress_factor)
                new_items.append(comp)
                compressed += 1
            # else: delivered + adequately mastered -> move on (item dropped).

            if perf.mastery < self.reinforce_below:
                # Rule 2: add a reinforcement item for the weak outcome.
                reinforce = PlanItem(
                    item_id=f"{new_plan_id}.reinforce.{it.item_id}",
                    title=f"Reinforcement: {it.title}",
                    outcomes=[OutcomeRef(o.outcome_id) for o in it.outcomes],
                    estimated_minutes=it.estimated_minutes,
                    priority=max(it.priority, 0) + self.rollover_priority,
                    reinforcement=True,
                )
                new_items.append(reinforce)
                reinforcements += 1

        adapted = Plan(
            plan_id=new_plan_id,
            scope=base.scope,
            owner_uuid=base.owner_uuid,
            subject_uuid=base.subject_uuid,
            items=new_items,
        )

        if self._events is not None:
            self._events.emit(
                EventType.PLAN_ADAPTED,
                subject_uuid=base.subject_uuid,
                payload={
                    "plan_id": new_plan_id,
                    "from_plan_id": base.plan_id,
                    "rolled_over": rolled,
                    "reinforcements": reinforcements,
                    "compressed": compressed,
                },
            )
        return adapted
