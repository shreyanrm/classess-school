"""Plans map to ontology outcomes and adapt to prior performance."""

import pytest

from planning.app.events import EventLog, EventType
from planning.app.plans import (
    OutcomeRef,
    Plan,
    PlanItem,
    PlanScope,
    PlanGenerator,
    PriorPerformance,
)


OWNER = "teacher-uuid"
SUBJECT = "class-uuid"


def _item(item_id, outcome_ids, minutes=40, priority=0):
    return PlanItem(
        item_id=item_id,
        title=f"Item {item_id}",
        outcomes=[OutcomeRef(outcome_id=o) for o in outcome_ids],
        estimated_minutes=minutes,
        priority=priority,
    )


# -- ontology mapping ----------------------------------------------------


def test_plan_is_fully_mapped_when_every_item_has_outcomes():
    gen = PlanGenerator()
    plan = gen.draft(
        "p1", PlanScope.DAILY, OWNER, SUBJECT,
        [_item("i1", ["o1"]), _item("i2", ["o2", "o3"])],
    )
    assert plan.is_fully_mapped()
    assert set(plan.mapped_outcome_ids()) == {"o1", "o2", "o3"}


def test_unmapped_item_is_flagged_not_silently_accepted():
    gen = PlanGenerator()
    plan = gen.draft(
        "p1", PlanScope.DAILY, OWNER, SUBJECT,
        [_item("i1", ["o1"]), _item("i2", [])],
    )
    assert not plan.is_fully_mapped()
    assert [it.item_id for it in plan.unmapped_items()] == ["i2"]


def test_outcome_resolver_flags_unresolved_refs():
    known = {"o1"}
    gen = PlanGenerator(resolve_outcome=lambda ref: ref.outcome_id in known)
    log = EventLog()
    gen_with_log = PlanGenerator(
        resolve_outcome=lambda ref: ref.outcome_id in known, event_log=log
    )
    gen_with_log.draft(
        "p1", PlanScope.DAILY, OWNER, SUBJECT,
        [_item("i1", ["o1"]), _item("i2", ["o-missing"])],
    )
    drafted = log.of_type(EventType.PLAN_DRAFTED)[0]
    assert drafted.payload["unresolved_outcomes"] == ["o-missing"]


def test_hierarchy_annual_unit_weekly_daily():
    annual = Plan("a", PlanScope.ANNUAL, OWNER, SUBJECT, [_item("ia", ["o1"])])
    unit = Plan("u", PlanScope.UNIT, OWNER, SUBJECT, [_item("iu", ["o2"])])
    annual.add_child(unit)
    assert annual.is_fully_mapped()
    assert set(annual.mapped_outcome_ids()) == {"o1", "o2"}
    # daily cannot parent annual
    daily = Plan("d", PlanScope.DAILY, OWNER, SUBJECT, [_item("id", ["o3"])])
    with pytest.raises(ValueError):
        daily.add_child(annual)


# -- adaptation ----------------------------------------------------------


def test_incomplete_item_rolls_forward():
    gen = PlanGenerator()
    base = gen.draft("p1", PlanScope.DAILY, OWNER, SUBJECT, [_item("i1", ["o1"])])
    prior = [PriorPerformance(outcome_id="o1", completed=False, mastery=0.5, item_id="i1")]
    nxt = gen.adapt(base, prior, "p2")
    rolled = [it for it in nxt.items if it.rolled_over_from == "i1"]
    assert len(rolled) == 1
    assert rolled[0].priority > 0  # prioritized


def test_weak_outcome_gets_reinforcement():
    gen = PlanGenerator(reinforce_below=0.6)
    base = gen.draft("p1", PlanScope.DAILY, OWNER, SUBJECT, [_item("i1", ["o1"])])
    prior = [PriorPerformance(outcome_id="o1", completed=True, mastery=0.3, item_id="i1")]
    nxt = gen.adapt(base, prior, "p2")
    reinforced = [it for it in nxt.items if it.reinforcement]
    assert len(reinforced) == 1
    assert "o1" in reinforced[0].outcome_ids


def test_strong_outcome_is_compressed():
    gen = PlanGenerator(compress_above=0.9)
    base = gen.draft(
        "p1", PlanScope.DAILY, OWNER, SUBJECT, [_item("i1", ["o1"], minutes=60)]
    )
    prior = [PriorPerformance(outcome_id="o1", completed=True, mastery=0.95, item_id="i1")]
    nxt = gen.adapt(base, prior, "p2")
    compressed = [it for it in nxt.items if it.compressed]
    assert len(compressed) == 1
    assert compressed[0].estimated_minutes < 60


def test_adapt_does_not_mutate_base_plan():
    gen = PlanGenerator()
    base = gen.draft("p1", PlanScope.DAILY, OWNER, SUBJECT, [_item("i1", ["o1"])])
    before = [it.item_id for it in base.items]
    gen.adapt(
        base,
        [PriorPerformance("o1", completed=False, mastery=0.2, item_id="i1")],
        "p2",
    )
    assert [it.item_id for it in base.items] == before


def test_adapt_emits_event_with_counts():
    log = EventLog()
    gen = PlanGenerator(event_log=log, reinforce_below=0.6, compress_above=0.9)
    base = gen.draft(
        "p1", PlanScope.DAILY, OWNER, SUBJECT,
        [_item("i1", ["o1"]), _item("i2", ["o2"], minutes=60), _item("i3", ["o3"])],
    )
    prior = [
        PriorPerformance("o1", completed=False, mastery=0.5, item_id="i1"),
        PriorPerformance("o2", completed=True, mastery=0.95, item_id="i2"),
        PriorPerformance("o3", completed=True, mastery=0.2, item_id="i3"),
    ]
    gen.adapt(base, prior, "p2")
    adapted = log.of_type(EventType.PLAN_ADAPTED)[0]
    assert adapted.payload["rolled_over"] == 1
    assert adapted.payload["compressed"] == 1
    assert adapted.payload["reinforcements"] >= 1
