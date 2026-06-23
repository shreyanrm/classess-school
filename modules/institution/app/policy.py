"""Policy inheritance down the hierarchy + hyperlocalization (B1).

A policy is a named, typed setting an institution governs (grading scheme,
attendance threshold, communication-language default, assessment-window rules,
data-retention window, and so on). Policies are set at any node in the
containment tree and INHERITED down it: a child node inherits its parent's
effective value and MAY override it locally. The nearest ancestor with a value
wins — resolution walks the node's path to the root nearest-first.

A policy may be sealed ``locked`` at a node: a locked policy is the floor a
group/region sets that descendants may NOT override (e.g. a child-safety or
data-retention minimum). Resolution records WHY a value won — which node set it
and whether it was a lock — because every effective setting must be explainable
(the laws' explainable-intelligence principle).

Hyperlocalization (language, region, calendar) is just policy with three
well-known keys, resolved the same inheritance way, so a region can default a
language and a school can refine it. No PII, no real board lock-in: a board /
calendar is a board-agnostic FIELD, never an enum of permitted boards.

Pure, import-safe: stdlib only. Consumes :mod:`app.hierarchy` for the path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .hierarchy import Hierarchy, Node


# Well-known hyperlocalization policy keys. These are CONFIG keys, not values —
# the values (which language, which calendar) are institution data, never
# hard-coded to one locale or board.
LOCALE_LANGUAGE = "locale.language"          # e.g. an IETF/ISO code as data
LOCALE_REGION = "locale.region"              # jurisdiction/region code as data
LOCALE_CALENDAR = "locale.calendar"          # academic-calendar handle as data
HYPERLOCALIZATION_KEYS = (LOCALE_LANGUAGE, LOCALE_REGION, LOCALE_CALENDAR)


class PolicyError(ValueError):
    """A policy rule was violated (overriding a locked policy, unknown node)."""


@dataclass(frozen=True)
class PolicyValue:
    """A single policy value set at a specific node.

    ``locked`` seals the value: descendants inherit it and may not override it.
    A locked value is the floor a higher node sets for everyone below.
    """

    key: str
    value: Any
    locked: bool = False


@dataclass(frozen=True)
class ResolvedPolicy:
    """The effective value of a policy at a node, with its provenance.

    Every field here exists so the setting is EXPLAINABLE: what value applies,
    which node set it (``source_node_id``), whether it came from the node itself
    or was inherited, and whether it is locked by an ancestor.
    """

    key: str
    value: Any
    source_node_id: str
    inherited: bool
    locked: bool

    @property
    def why(self) -> str:
        """Plain-language explanation of why this value applies."""
        origin = "inherited from an ancestor node" if self.inherited else "set on this node"
        seal = "; locked by that node so it cannot be overridden below" if self.locked else ""
        return f"value {self.value!r} for {self.key!r} ({origin}){seal}."


class PolicySet:
    """Policies set across a hierarchy, plus the inheritance resolver.

    Policies are stored per node. Resolution for a node walks ``path_to_root``
    nearest-first; the first node that sets the key wins UNLESS a node above it
    locked the key, in which case the lock (the highest locked setter on the
    path) wins. Setting a key locally that an ancestor locked is rejected.
    """

    def __init__(self, hierarchy: Hierarchy) -> None:
        self._hierarchy = hierarchy
        # node_id -> { key -> PolicyValue }
        self._by_node: dict[str, dict[str, PolicyValue]] = {}

    # -- mutation -----------------------------------------------------------
    def set_policy(
        self,
        node_id: str,
        key: str,
        value: Any,
        *,
        locked: bool = False,
    ) -> PolicyValue:
        """Set a policy at a node.

        Rejected if an ANCESTOR has locked the same key — a locked policy is a
        floor a descendant may not override (INVARIANT-adjacent governance: the
        most powerful settings stay the best-governed).
        """
        # Validate the node exists (raises KeyError if not).
        self._hierarchy.get_node(node_id)
        ancestor_lock = self._locked_ancestor(node_id, key)
        if ancestor_lock is not None:
            raise PolicyError(
                f"Policy {key!r} is locked by an ancestor node "
                f"({ancestor_lock!r}); it cannot be overridden at {node_id!r}."
            )
        pv = PolicyValue(key=key, value=value, locked=locked)
        self._by_node.setdefault(node_id, {})[key] = pv
        return pv

    def _locked_ancestor(self, node_id: str, key: str) -> Optional[str]:
        """The id of the nearest STRICT ancestor that locked ``key``, or None."""
        for ancestor in self._hierarchy.ancestors(node_id):
            pv = self._by_node.get(ancestor.id, {}).get(key)
            if pv is not None and pv.locked:
                return ancestor.id
        return None

    # -- resolution ---------------------------------------------------------
    def resolve(self, node_id: str, key: str) -> Optional[ResolvedPolicy]:
        """Resolve the effective value of ``key`` at ``node_id``.

        A lock set anywhere above a node wins over a nearer unlocked value: the
        HIGHEST locked setter on the path is the floor. Otherwise the NEAREST
        setter on the path (the node itself first) wins. Returns ``None`` if the
        key is set nowhere on the path.
        """
        path = self._hierarchy.path_to_root(node_id)  # nearest-first incl. self

        # A lock anywhere above is binding; the highest (root-most) lock wins,
        # because a region's lock outranks a campus's lock.
        locked_setter: Optional[tuple[Node, PolicyValue]] = None
        for node in path:
            pv = self._by_node.get(node.id, {}).get(key)
            if pv is not None and pv.locked:
                locked_setter = (node, pv)  # keep overwriting -> ends at highest
        if locked_setter is not None:
            node, pv = locked_setter
            return ResolvedPolicy(
                key=key,
                value=pv.value,
                source_node_id=node.id,
                inherited=(node.id != node_id),
                locked=True,
            )

        # No lock: nearest setter wins.
        for node in path:
            pv = self._by_node.get(node.id, {}).get(key)
            if pv is not None:
                return ResolvedPolicy(
                    key=key,
                    value=pv.value,
                    source_node_id=node.id,
                    inherited=(node.id != node_id),
                    locked=False,
                )
        return None

    def effective(self, node_id: str) -> dict[str, ResolvedPolicy]:
        """Every policy in force at a node, resolved with provenance.

        The union of keys set anywhere on the node's path, each resolved to the
        value that actually applies. This is the explainable "what governs this
        section" view.
        """
        keys: set[str] = set()
        for node in self._hierarchy.path_to_root(node_id):
            keys.update(self._by_node.get(node.id, {}).keys())
        out: dict[str, ResolvedPolicy] = {}
        for key in keys:
            resolved = self.resolve(node_id, key)
            if resolved is not None:
                out[key] = resolved
        return out

    def localization(self, node_id: str) -> dict[str, Optional[ResolvedPolicy]]:
        """Resolve the three hyperlocalization keys (language, region, calendar)
        for a node. A missing key resolves to ``None`` (no default invented)."""
        return {key: self.resolve(node_id, key) for key in HYPERLOCALIZATION_KEYS}


@dataclass(frozen=True)
class LocalizationConfig:
    """A flattened, plain hyperlocalization view for a node.

    Holds only the resolved VALUES (language / region / calendar) for the
    surface to render. Any may be ``None`` — the module never invents a locale
    default; an unset language stays unset for the institution to choose.
    """

    node_id: str
    language: Optional[str] = None
    region: Optional[str] = None
    calendar: Optional[str] = None

    @classmethod
    def from_policy_set(cls, policies: PolicySet, node_id: str) -> "LocalizationConfig":
        loc = policies.localization(node_id)

        def _val(key: str) -> Optional[str]:
            rp = loc.get(key)
            return None if rp is None else rp.value

        return cls(
            node_id=node_id,
            language=_val(LOCALE_LANGUAGE),
            region=_val(LOCALE_REGION),
            calendar=_val(LOCALE_CALENDAR),
        )
