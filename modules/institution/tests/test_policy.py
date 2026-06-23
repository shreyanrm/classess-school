"""Policy inheritance + override + locking, and hyperlocalization resolution."""

from __future__ import annotations

import pytest

from app.hierarchy import build_hierarchy
from app.policy import (
    PolicySet,
    PolicyError,
    LocalizationConfig,
    LOCALE_LANGUAGE,
    LOCALE_REGION,
    LOCALE_CALENDAR,
)


def _hierarchy():
    spec = [
        {"key": "g", "kind": "group", "label": "Example Group", "parent": None},
        {"key": "r", "kind": "region", "label": "Region West", "parent": "g"},
        {"key": "s", "kind": "school", "label": "Senior School", "parent": "r"},
        {"key": "sec", "kind": "section", "label": "Section 10-B", "parent": "s"},
    ]
    h = build_hierarchy("tenant-A", spec)
    ids = {n.label: n.id for n in h.all_nodes()}
    return h, ids


def test_child_inherits_parent_policy():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    ps.set_policy(ids["Example Group"], "grading.scheme", "competency-based")

    resolved = ps.resolve(ids["Section 10-B"], "grading.scheme")
    assert resolved is not None
    assert resolved.value == "competency-based"
    assert resolved.inherited is True
    assert resolved.source_node_id == ids["Example Group"]
    assert "inherited" in resolved.why


def test_child_can_override_parent():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    ps.set_policy(ids["Example Group"], "attendance.threshold", 0.75)
    ps.set_policy(ids["Senior School"], "attendance.threshold", 0.85)

    # Nearest setter wins: the section inherits the school's override.
    resolved = ps.resolve(ids["Section 10-B"], "attendance.threshold")
    assert resolved.value == 0.85
    assert resolved.source_node_id == ids["Senior School"]
    assert resolved.inherited is True

    # The group still sees its own value.
    at_group = ps.resolve(ids["Example Group"], "attendance.threshold")
    assert at_group.value == 0.75
    assert at_group.inherited is False


def test_locked_policy_cannot_be_overridden():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    # The region locks a data-retention floor.
    ps.set_policy(ids["Region West"], "retention.months", 36, locked=True)
    with pytest.raises(PolicyError):
        ps.set_policy(ids["Senior School"], "retention.months", 6)

    # The lock is the effective value below, marked locked + explainable.
    resolved = ps.resolve(ids["Section 10-B"], "retention.months")
    assert resolved.value == 36
    assert resolved.locked is True
    assert resolved.source_node_id == ids["Region West"]
    assert "locked" in resolved.why


def test_highest_lock_wins_over_nearer_unlocked():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    # Group sets unlocked; region locks. Region (higher locked) wins below it.
    ps.set_policy(ids["Example Group"], "safety.min", "strict", locked=True)
    # A locked group value cannot be overridden at the region either.
    with pytest.raises(PolicyError):
        ps.set_policy(ids["Region West"], "safety.min", "lenient")
    resolved = ps.resolve(ids["Section 10-B"], "safety.min")
    assert resolved.value == "strict"
    assert resolved.locked is True


def test_unset_policy_resolves_none():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    assert ps.resolve(ids["Section 10-B"], "nothing.here") is None


def test_effective_collects_full_set_with_provenance():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    ps.set_policy(ids["Example Group"], "grading.scheme", "competency-based")
    ps.set_policy(ids["Senior School"], "attendance.threshold", 0.85)
    eff = ps.effective(ids["Section 10-B"])
    assert set(eff) == {"grading.scheme", "attendance.threshold"}
    assert eff["grading.scheme"].inherited is True
    assert eff["attendance.threshold"].value == 0.85


def test_hyperlocalization_inherits_and_refines():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    # Region defaults a language; school refines it; calendar set at group.
    ps.set_policy(ids["Region West"], LOCALE_LANGUAGE, "lang-default")
    ps.set_policy(ids["Senior School"], LOCALE_LANGUAGE, "lang-refined")
    ps.set_policy(ids["Example Group"], LOCALE_CALENDAR, "calendar-handle")

    loc = LocalizationConfig.from_policy_set(ps, ids["Section 10-B"])
    assert loc.language == "lang-refined"   # nearest refinement
    assert loc.calendar == "calendar-handle"  # inherited from the group
    assert loc.region is None  # never invented when unset


def test_localization_no_default_invented():
    h, ids = _hierarchy()
    ps = PolicySet(h)
    loc = LocalizationConfig.from_policy_set(ps, ids["Section 10-B"])
    assert loc.language is None and loc.region is None and loc.calendar is None
