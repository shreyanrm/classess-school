"""Hierarchy build + traversal, and the scoped, time-bound relationship graph."""

from __future__ import annotations

from datetime import date

import pytest

from app.hierarchy import (
    Hierarchy,
    HierarchyError,
    build_hierarchy,
    NODE_LADDER,
    rank_of,
)
from app.tenancy import TenantScope, CrossTenantAccessError


def _full_ladder_spec() -> list[dict]:
    return [
        {"key": "g", "kind": "group", "label": "Example Group", "parent": None},
        {"key": "r", "kind": "region", "label": "Region West", "parent": "g"},
        {"key": "c", "kind": "campus", "label": "Campus North", "parent": "r"},
        {"key": "s", "kind": "school", "label": "Senior School", "parent": "c"},
        {"key": "d", "kind": "department", "label": "Sciences", "parent": "s"},
        {"key": "gr", "kind": "grade", "label": "Grade 10", "parent": "d"},
        {"key": "sec", "kind": "section", "label": "Section 10-B", "parent": "gr"},
    ]


def test_ladder_is_coarsest_to_finest():
    assert NODE_LADDER[0] == "group"
    assert NODE_LADDER[-1] == "section"
    assert rank_of("group") < rank_of("section")


def test_build_full_ladder_and_traverse():
    h = build_hierarchy("tenant-A", _full_ladder_spec())
    assert len(h.all_nodes()) == 7
    roots = h.roots()
    assert len(roots) == 1 and roots[0].kind == "group"

    # Find the section and walk to root.
    section = next(n for n in h.all_nodes() if n.kind == "section")
    path = h.path_to_root(section.id)
    kinds = [n.kind for n in path]
    # Nearest-first, self included.
    assert kinds == [
        "section", "grade", "department", "school", "campus", "region", "group",
    ]


def test_ancestors_nearest_first_excludes_self():
    h = build_hierarchy("tenant-A", _full_ladder_spec())
    section = next(n for n in h.all_nodes() if n.kind == "section")
    anc = h.ancestors(section.id)
    assert anc[0].kind == "grade"
    assert anc[-1].kind == "group"
    assert section.id not in {n.id for n in anc}


def test_descendants_of_root_covers_all_but_root():
    h = build_hierarchy("tenant-A", _full_ladder_spec())
    root = h.roots()[0]
    desc = h.descendants(root.id)
    assert len(desc) == 6  # all but the root


def test_configurable_subset_ladder():
    # An institution may skip rungs: a school straight to grades and sections.
    spec = [
        {"key": "s", "kind": "school", "label": "Day School", "parent": None},
        {"key": "g10", "kind": "grade", "label": "Grade 10", "parent": "s"},
        {"key": "a", "kind": "section", "label": "Section 10-A", "parent": "g10"},
    ]
    h = build_hierarchy("tenant-A", spec)
    assert len(h.all_nodes()) == 3
    assert h.roots()[0].kind == "school"


def test_parent_must_outrank_child():
    h = Hierarchy("tenant-A")
    grade = h.add_node(kind="grade", label="Grade 10")
    with pytest.raises(HierarchyError):
        # A grade cannot contain a campus (child out-ranks parent).
        h.add_node(kind="campus", label="Campus North", parent_id=grade.id)


def test_unknown_kind_rejected():
    h = Hierarchy("tenant-A")
    with pytest.raises(ValueError):
        h.add_node(kind="planet", label="nope")


def test_relationship_is_time_bound():
    h = build_hierarchy("tenant-A", _full_ladder_spec())
    dept = next(n for n in h.all_nodes() if n.kind == "department")
    school = next(n for n in h.all_nodes() if n.kind == "school")
    rel = h.add_relationship(
        kind="shared_department",
        source_id=dept.id,
        target_id=school.id,
        valid_from=date(2026, 4, 1),
        valid_to=date(2026, 10, 1),
    )
    assert rel.active_on(date(2026, 6, 1)) is True
    assert rel.active_on(date(2026, 1, 1)) is False   # before window
    assert rel.active_on(date(2026, 10, 1)) is False  # to is exclusive

    # as_of filtering on lookups.
    assert h.relationships_of(dept.id, as_of=date(2026, 6, 1))
    assert not h.relationships_of(dept.id, as_of=date(2027, 1, 1))


def test_relationship_many_to_many_related_nodes():
    h = build_hierarchy("tenant-A", _full_ladder_spec())
    nodes = {n.kind: n for n in h.all_nodes()}
    # A coordination edge from region scoping the school.
    h.add_relationship(
        kind="coordination",
        source_id=nodes["region"].id,
        target_id=nodes["school"].id,
        valid_from=date(2026, 4, 1),
    )
    related = h.related_nodes(nodes["region"].id, as_of=date(2026, 5, 1))
    assert nodes["school"].id in {n.id for n in related}


def test_relationship_endpoints_must_exist_and_differ():
    h = build_hierarchy("tenant-A", _full_ladder_spec())
    a = h.all_nodes()[0]
    with pytest.raises(HierarchyError):
        h.add_relationship(
            kind="feeder", source_id=a.id, target_id="missing",
            valid_from=date(2026, 4, 1),
        )
    with pytest.raises(HierarchyError):
        h.add_relationship(
            kind="feeder", source_id=a.id, target_id=a.id,
            valid_from=date(2026, 4, 1),
        )


def test_invalid_relationship_window_rejected():
    h = build_hierarchy("tenant-A", _full_ladder_spec())
    a, b = h.all_nodes()[0], h.all_nodes()[1]
    with pytest.raises(ValueError):
        h.add_relationship(
            kind="feeder", source_id=a.id, target_id=b.id,
            valid_from=date(2026, 4, 1), valid_to=date(2026, 4, 1),
        )


def test_get_node_is_tenant_guarded():
    h = build_hierarchy("tenant-A", _full_ladder_spec())
    node = h.all_nodes()[0]
    # An actor in another tenant cannot read this node.
    foreign = TenantScope(tenant_id="tenant-B")
    with pytest.raises(CrossTenantAccessError):
        h.get_node(node.id, scope=foreign)
    # The owning tenant can.
    assert h.get_node(node.id, scope=TenantScope(tenant_id="tenant-A")).id == node.id
