"""The org hierarchy + scoped, time-bound relationship graph (B1).

Board-agnostic by construction. The node kinds are the configurable spine of an
institution:

    group -> region -> campus -> school -> department -> grade -> section

but the ladder is CONFIGURABLE, not hard-coded: an institution may use only a
subset (a single school with grades and sections), skip rungs (a campus straight
to grades), or rename the display label while keeping the canonical kind. No
real board, no real campus name appears here — kinds are structural, labels are
data.

Two graphs live here:

  1. The CONTAINMENT tree — a node has at most one structural parent, and a
     parent's kind must out-rank the child's kind on the configured ladder. This
     is the "where does this section sit" tree that policy inherits down.

  2. The RELATIONSHIP graph — many-to-many, SCOPED and TIME-BOUND edges between
     nodes that are NOT pure containment: a teacher's department shared across
     two campuses, a combined section that draws from two grades, a region-level
     coordinator scoped to a set of schools for a term. Each edge carries a
     ``valid_from`` / ``valid_to`` window so the graph is correct as of a date,
     and a scope so a relationship never silently spans tenants.

Every node and edge carries the opaque ``tenant_id`` (INVARIANT 10). No PII: a
node is a structural unit, not a person; people attach through the roster
(opaque ``canonical_uuid`` only). Pure, import-safe: stdlib only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional

from .tenancy import TenantScope, guard_read


# The configurable node ladder, coarsest -> finest. Index = rank; a parent must
# out-rank (lower index) its child. Board-agnostic: these are STRUCTURAL kinds,
# never an enum of permitted boards or real institutions.
NODE_LADDER: tuple[str, ...] = (
    "group",
    "region",
    "campus",
    "school",
    "department",
    "grade",
    "section",
)
_RANK = {kind: i for i, kind in enumerate(NODE_LADDER)}


def is_node_kind(kind: str) -> bool:
    return kind in _RANK


def rank_of(kind: str) -> int:
    if kind not in _RANK:
        raise ValueError(
            f"Unknown node kind {kind!r}. Configurable ladder is: {', '.join(NODE_LADDER)}."
        )
    return _RANK[kind]


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class Node:
    """A structural unit in the org tree. Carries an opaque tenant scope.

    ``kind`` is a canonical rung of :data:`NODE_LADDER`; ``label`` is the
    institution's own display name (data, never hard-coded). ``parent_id`` is the
    single structural parent (``None`` for the root). No PII — a node is a place,
    not a person.
    """

    id: str
    tenant_id: str
    kind: str
    label: str
    parent_id: Optional[str] = None
    # Free-form structural attributes (e.g. medium of instruction at a school,
    # capacity of a section). Never PII.
    attributes: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not is_node_kind(self.kind):
            raise ValueError(
                f"Unknown node kind {self.kind!r}. Configurable ladder is: "
                f"{', '.join(NODE_LADDER)}."
            )


# The kinds of cross-cutting relationship the many-to-many graph models. These
# are NOT containment — containment is the tree's parent edge.
RELATIONSHIP_KINDS: tuple[str, ...] = (
    "shared_department",   # one department serves several campuses/schools
    "combined_section",    # a section drawing learners from >1 grade
    "feeder",              # one node feeds learners into another (campus -> school)
    "coordination",        # a coordinating node scoped over a set of nodes
    "affiliation",         # a node affiliated to another (board/exam centre)
)


@dataclass(frozen=True)
class Relationship:
    """A many-to-many, SCOPED, TIME-BOUND edge between two nodes.

    ``valid_from`` is inclusive; ``valid_to`` is exclusive and may be ``None``
    (open-ended). The edge is only "active as of" a date inside that window. The
    edge carries its own ``tenant_id`` and must connect two nodes in the same
    tenant — a relationship never silently spans tenants (INVARIANT 10).
    """

    id: str
    tenant_id: str
    kind: str
    source_id: str
    target_id: str
    valid_from: date
    valid_to: Optional[date] = None
    attributes: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in RELATIONSHIP_KINDS:
            raise ValueError(
                f"Unknown relationship kind {self.kind!r}. Known: "
                f"{', '.join(RELATIONSHIP_KINDS)}."
            )
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be strictly after valid_from.")

    def active_on(self, as_of: date) -> bool:
        """True iff this edge is in force on ``as_of`` (from inclusive, to exclusive)."""
        if as_of < self.valid_from:
            return False
        if self.valid_to is not None and as_of >= self.valid_to:
            return False
        return True


class HierarchyError(ValueError):
    """A structural rule was violated (bad parent rank, cycle, cross-tenant edge)."""


class Hierarchy:
    """A single institution's org hierarchy: the containment tree plus the
    scoped, time-bound relationship graph.

    Every mutation enforces the structural rules so the tree can never become
    invalid: one parent per node, a parent out-ranks its child, no cycles, and
    every node/edge is in this hierarchy's tenant. Reads are tenant-guarded.
    """

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self._nodes: dict[str, Node] = {}
        self._children: dict[str, list[str]] = {}
        self._relationships: dict[str, Relationship] = {}

    # -- node construction --------------------------------------------------
    def add_node(
        self,
        *,
        kind: str,
        label: str,
        parent_id: Optional[str] = None,
        node_id: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> Node:
        """Add a node under ``parent_id`` (or as a root when ``None``).

        Enforces: known kind, parent in this hierarchy, parent out-ranks child,
        no duplicate id.
        """
        node = Node(
            id=node_id or _new_id(),
            tenant_id=self.tenant_id,
            kind=kind,
            label=label,
            parent_id=parent_id,
            attributes=dict(attributes or {}),
        )
        if node.id in self._nodes:
            raise HierarchyError(f"Node id {node.id!r} already exists.")
        if parent_id is not None:
            parent = self._nodes.get(parent_id)
            if parent is None:
                raise HierarchyError(f"Parent {parent_id!r} not found in this hierarchy.")
            if rank_of(parent.kind) >= rank_of(node.kind):
                raise HierarchyError(
                    f"A {parent.kind!r} cannot contain a {node.kind!r}: a parent "
                    f"must out-rank its child on the configured ladder."
                )
        self._nodes[node.id] = node
        self._children.setdefault(node.id, [])
        if parent_id is not None:
            self._children[parent_id].append(node.id)
        return node

    # -- relationship construction -----------------------------------------
    def add_relationship(
        self,
        *,
        kind: str,
        source_id: str,
        target_id: str,
        valid_from: date,
        valid_to: Optional[date] = None,
        rel_id: Optional[str] = None,
        attributes: Optional[dict] = None,
    ) -> Relationship:
        """Add a scoped, time-bound many-to-many edge between two existing nodes.

        Both endpoints must exist in THIS hierarchy (same tenant) — a
        relationship never spans tenants.
        """
        for endpoint in (source_id, target_id):
            if endpoint not in self._nodes:
                raise HierarchyError(f"Relationship endpoint {endpoint!r} not found.")
        if source_id == target_id:
            raise HierarchyError("A relationship must connect two distinct nodes.")
        rel = Relationship(
            id=rel_id or _new_id(),
            tenant_id=self.tenant_id,
            kind=kind,
            source_id=source_id,
            target_id=target_id,
            valid_from=valid_from,
            valid_to=valid_to,
            attributes=dict(attributes or {}),
        )
        if rel.id in self._relationships:
            raise HierarchyError(f"Relationship id {rel.id!r} already exists.")
        self._relationships[rel.id] = rel
        return rel

    # -- reads (tenant-guarded) --------------------------------------------
    def get_node(self, node_id: str, *, scope: Optional[TenantScope] = None) -> Node:
        node = self._nodes.get(node_id)
        if node is None:
            raise KeyError(node_id)
        if scope is not None:
            guard_read(scope, node)
        return node

    def children(self, node_id: str) -> list[Node]:
        """Direct structural children of a node, in insertion order."""
        return [self._nodes[c] for c in self._children.get(node_id, [])]

    def roots(self) -> list[Node]:
        return [n for n in self._nodes.values() if n.parent_id is None]

    def ancestors(self, node_id: str) -> list[Node]:
        """The containment chain from the node's parent up to the root.

        Ordered NEAREST-first (immediate parent, then up). This is the order
        policy inheritance walks — the nearest ancestor's override wins.
        """
        chain: list[Node] = []
        current = self._nodes.get(node_id)
        if current is None:
            raise KeyError(node_id)
        seen = {current.id}
        while current.parent_id is not None:
            parent = self._nodes.get(current.parent_id)
            if parent is None:
                raise HierarchyError(
                    f"Dangling parent {current.parent_id!r} for node {current.id!r}."
                )
            if parent.id in seen:
                raise HierarchyError(f"Cycle detected at node {parent.id!r}.")
            chain.append(parent)
            seen.add(parent.id)
            current = parent
        return chain

    def path_to_root(self, node_id: str) -> list[Node]:
        """The full chain INCLUDING the node itself, nearest-first to the root."""
        return [self.get_node(node_id)] + self.ancestors(node_id)

    def descendants(self, node_id: str) -> list[Node]:
        """All structural descendants of a node (depth-first, pre-order)."""
        out: list[Node] = []
        stack = list(reversed(self._children.get(node_id, [])))
        while stack:
            cid = stack.pop()
            out.append(self._nodes[cid])
            stack.extend(reversed(self._children.get(cid, [])))
        return out

    def relationships_of(
        self,
        node_id: str,
        *,
        kind: Optional[str] = None,
        as_of: Optional[date] = None,
        direction: str = "both",
    ) -> list[Relationship]:
        """Relationship edges touching ``node_id``.

        ``as_of`` filters to edges active on that date (the time-bound rule);
        omit it to get every edge regardless of window. ``direction`` is
        ``"out"`` (source), ``"in"`` (target), or ``"both"``.
        """
        if direction not in ("out", "in", "both"):
            raise ValueError("direction must be 'out', 'in', or 'both'.")
        out: list[Relationship] = []
        for rel in self._relationships.values():
            touches = (
                (direction in ("out", "both") and rel.source_id == node_id)
                or (direction in ("in", "both") and rel.target_id == node_id)
            )
            if not touches:
                continue
            if kind is not None and rel.kind != kind:
                continue
            if as_of is not None and not rel.active_on(as_of):
                continue
            out.append(rel)
        return out

    def related_nodes(
        self,
        node_id: str,
        *,
        kind: Optional[str] = None,
        as_of: Optional[date] = None,
    ) -> list[Node]:
        """The nodes reached by active relationship edges from ``node_id``."""
        out: list[Node] = []
        for rel in self.relationships_of(node_id, kind=kind, as_of=as_of):
            other_id = rel.target_id if rel.source_id == node_id else rel.source_id
            out.append(self._nodes[other_id])
        return out

    def all_nodes(self) -> list[Node]:
        return list(self._nodes.values())

    def all_relationships(self) -> list[Relationship]:
        return list(self._relationships.values())


def build_hierarchy(tenant_id: str, spec: Iterable[dict]) -> Hierarchy:
    """Build a :class:`Hierarchy` from a flat, ordered spec of node dicts.

    Each dict: ``{"key": <stable handle>, "kind": ..., "label": ...,
    "parent": <key|None>, "attributes": {...}}``. ``key`` is the caller's stable
    handle used to wire parents; ids are minted opaque. Parents must appear
    before children. Returns the populated hierarchy.
    """
    h = Hierarchy(tenant_id)
    key_to_id: dict[str, str] = {}
    for entry in spec:
        key = entry["key"]
        parent_key = entry.get("parent")
        parent_id = key_to_id[parent_key] if parent_key is not None else None
        node = h.add_node(
            kind=entry["kind"],
            label=entry["label"],
            parent_id=parent_id,
            attributes=entry.get("attributes"),
        )
        key_to_id[key] = node.id
    return h
