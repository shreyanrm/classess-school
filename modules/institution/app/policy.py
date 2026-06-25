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

VERSIONING + EFFECTIVE DATES (spec /admin/policies: "versioned with effective
dates + audit"). Setting a policy at a node never overwrites: it APPENDS a new
:class:`PolicyVersion` (monotonic version number, ``effective_from`` date,
``recorded_at`` timestamp, optional human note). Resolution is "as of" a date —
the latest version whose ``effective_from`` is on/before the as-of date wins —
so a school can stage next-year's grading change today and it takes effect on
the year boundary, and the full history stays queryable for audit. This mirrors
the events' append-only law: history is never mutated, only extended.

Hyperlocalization (language, region, calendar, BOARD TERMINOLOGY, LOCAL EXAM
FORMAT) is just policy with well-known keys, resolved the same inheritance +
effective-date way, so a region can default a language and a school can refine
it. No PII, no real board lock-in: a board / calendar / exam format is a
board-agnostic FIELD whose VALUE is institution data, never an enum of permitted
boards. Board terminology lets an institution map the platform's structural
vocabulary onto its own labels ("Standard" for grade, "Division" for section)
without hard-coding any one board's words.

Pure, import-safe: stdlib only. Consumes :mod:`app.hierarchy` for the path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable, Optional

from .hierarchy import Hierarchy, Node


# Well-known hyperlocalization policy keys. These are CONFIG keys, not values —
# the values (which language, which calendar, which words a board uses) are
# institution data, never hard-coded to one locale or board.
LOCALE_LANGUAGE = "locale.language"          # e.g. an IETF/ISO code as data
LOCALE_REGION = "locale.region"              # jurisdiction/region code as data
LOCALE_CALENDAR = "locale.calendar"          # academic-calendar handle as data
# Board terminology: a mapping from the platform's structural vocabulary to the
# institution's own words ({"grade": "Standard", "section": "Division", ...}).
# The VALUE is the institution's data; no board's words are hard-coded.
LOCALE_BOARD_TERMS = "locale.board_terms"
# Local exam format: a board-agnostic descriptor of how this locale assesses
# (e.g. {"name": "...", "components": [...], "grade_scale": "..."}) — data, not
# an enum of permitted boards.
LOCALE_EXAM_FORMAT = "locale.exam_format"
HYPERLOCALIZATION_KEYS = (
    LOCALE_LANGUAGE,
    LOCALE_REGION,
    LOCALE_CALENDAR,
    LOCALE_BOARD_TERMS,
    LOCALE_EXAM_FORMAT,
)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PolicyError(ValueError):
    """A policy rule was violated (overriding a locked policy, unknown node)."""


@dataclass(frozen=True)
class PolicyVersion:
    """One immutable version of a policy value set at a node.

    Versions are append-only per (node, key). ``version`` is a 1-based monotonic
    counter; ``effective_from`` is the date the value starts applying (resolution
    is "as of" a date); ``recorded_at`` is when it was entered (audit); ``note``
    is an optional human reason. ``locked`` seals the value: descendants inherit
    it and may not override it.
    """

    key: str
    value: Any
    version: int
    effective_from: date
    recorded_at: str
    locked: bool = False
    note: Optional[str] = None


@dataclass(frozen=True)
class ResolvedPolicy:
    """The effective value of a policy at a node, with its provenance.

    Every field here exists so the setting is EXPLAINABLE: what value applies,
    which node set it (``source_node_id``), whether it came from the node itself
    or was inherited, whether it is locked by an ancestor, and WHICH version /
    effective date won (so an audit can trace it).
    """

    key: str
    value: Any
    source_node_id: str
    inherited: bool
    locked: bool
    version: int
    effective_from: date

    @property
    def why(self) -> str:
        """Plain-language explanation of why this value applies."""
        origin = "inherited from an ancestor node" if self.inherited else "set on this node"
        seal = "; locked by that node so it cannot be overridden below" if self.locked else ""
        return (
            f"value {self.value!r} for {self.key!r} ({origin}, "
            f"version {self.version} effective {self.effective_from.isoformat()}){seal}."
        )


class PolicySet:
    """Policies set across a hierarchy, plus the inheritance + effective-date
    resolver.

    Policy versions are stored per node, append-only. Resolution for a node
    walks ``path_to_root`` nearest-first; at each node the version effective
    AS-OF the resolution date is taken; the first node that has an effective
    value wins UNLESS a node above it locked the key, in which case the lock
    (the highest locked setter on the path, as-of the date) wins. Setting a key
    locally that an ancestor locked is rejected.
    """

    def __init__(self, hierarchy: Hierarchy) -> None:
        self._hierarchy = hierarchy
        # node_id -> { key -> [PolicyVersion, ...] }  (append-only, version-ordered)
        self._by_node: dict[str, dict[str, list[PolicyVersion]]] = {}

    # -- mutation -----------------------------------------------------------
    def set_policy(
        self,
        node_id: str,
        key: str,
        value: Any,
        *,
        locked: bool = False,
        effective_from: Optional[date] = None,
        note: Optional[str] = None,
    ) -> PolicyVersion:
        """Set (APPEND a version of) a policy at a node.

        Never overwrites: appends a new :class:`PolicyVersion` with the next
        version number and the given ``effective_from`` (defaulting to today, so
        a plain set takes effect immediately). Staging a future ``effective_from``
        schedules the change; history stays queryable.

        Rejected if an ANCESTOR has the key locked (effective as of the new
        version's ``effective_from``) — a locked policy is a floor a descendant
        may not override (governance: the most powerful settings stay the
        best-governed). A node may continue to version its OWN locked key.
        """
        # Validate the node exists (raises KeyError if not).
        self._hierarchy.get_node(node_id)
        eff = effective_from or _today()
        ancestor_lock = self._locked_ancestor(node_id, key, eff)
        if ancestor_lock is not None:
            raise PolicyError(
                f"Policy {key!r} is locked by an ancestor node "
                f"({ancestor_lock!r}); it cannot be overridden at {node_id!r}."
            )
        history = self._by_node.setdefault(node_id, {}).setdefault(key, [])
        pv = PolicyVersion(
            key=key,
            value=value,
            version=len(history) + 1,
            effective_from=eff,
            recorded_at=_now_iso(),
            locked=locked,
            note=note,
        )
        history.append(pv)
        return pv

    def _effective_version_at(
        self, node_id: str, key: str, as_of: date
    ) -> Optional[PolicyVersion]:
        """The version of ``key`` SET ON ``node_id`` in force on ``as_of``.

        The latest version whose ``effective_from`` is on/before ``as_of``.
        Returns ``None`` if the node never set the key, or all versions start
        after ``as_of`` (nothing in force yet).
        """
        history = self._by_node.get(node_id, {}).get(key)
        if not history:
            return None
        in_force = [pv for pv in history if pv.effective_from <= as_of]
        if not in_force:
            return None
        # Latest effective_from wins; ties broken by version (later record wins).
        return max(in_force, key=lambda pv: (pv.effective_from, pv.version))

    def _locked_ancestor(
        self, node_id: str, key: str, as_of: date
    ) -> Optional[str]:
        """The id of the nearest STRICT ancestor whose effective value (as of
        ``as_of``) locks ``key``, or ``None``."""
        for ancestor in self._hierarchy.ancestors(node_id):
            pv = self._effective_version_at(ancestor.id, key, as_of)
            if pv is not None and pv.locked:
                return ancestor.id
        return None

    # -- resolution ---------------------------------------------------------
    def resolve(
        self, node_id: str, key: str, *, as_of: Optional[date] = None
    ) -> Optional[ResolvedPolicy]:
        """Resolve the effective value of ``key`` at ``node_id`` as of a date.

        ``as_of`` defaults to today. At each node on the path the version in
        force on ``as_of`` is taken. A lock set anywhere above a node wins over a
        nearer unlocked value: the HIGHEST locked setter on the path is the
        floor. Otherwise the NEAREST setter on the path (the node itself first)
        wins. Returns ``None`` if the key is in force nowhere on the path.
        """
        when = as_of or _today()
        path = self._hierarchy.path_to_root(node_id)  # nearest-first incl. self

        # A lock anywhere above is binding; the highest (root-most) lock wins,
        # because a region's lock outranks a campus's lock.
        locked_setter: Optional[tuple[Node, PolicyVersion]] = None
        for node in path:
            pv = self._effective_version_at(node.id, key, when)
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
                version=pv.version,
                effective_from=pv.effective_from,
            )

        # No lock: nearest setter wins.
        for node in path:
            pv = self._effective_version_at(node.id, key, when)
            if pv is not None:
                return ResolvedPolicy(
                    key=key,
                    value=pv.value,
                    source_node_id=node.id,
                    inherited=(node.id != node_id),
                    locked=False,
                    version=pv.version,
                    effective_from=pv.effective_from,
                )
        return None

    def effective(
        self, node_id: str, *, as_of: Optional[date] = None
    ) -> dict[str, ResolvedPolicy]:
        """Every policy in force at a node, resolved with provenance, as of a date.

        The union of keys ever set anywhere on the node's path, each resolved to
        the value that actually applies on ``as_of``. This is the explainable
        "what governs this section right now" view.
        """
        when = as_of or _today()
        keys: set[str] = set()
        for node in self._hierarchy.path_to_root(node_id):
            keys.update(self._by_node.get(node.id, {}).keys())
        out: dict[str, ResolvedPolicy] = {}
        for key in keys:
            resolved = self.resolve(node_id, key, as_of=when)
            if resolved is not None:
                out[key] = resolved
        return out

    def history(self, node_id: str, key: str) -> list[PolicyVersion]:
        """The full append-only version history of ``key`` SET ON ``node_id``.

        Version-ordered (oldest first). The queryable audit trail behind every
        policy change — never mutated, only extended."""
        return list(self._by_node.get(node_id, {}).get(key, []))

    def set_versions(self, node_id: str) -> dict[str, list[PolicyVersion]]:
        """Every key+history set LOCALLY on a node (for the audit/policy table)."""
        return {k: list(v) for k, v in self._by_node.get(node_id, {}).items()}

    def localization(
        self, node_id: str, *, as_of: Optional[date] = None
    ) -> dict[str, Optional[ResolvedPolicy]]:
        """Resolve the hyperlocalization keys (language, region, calendar, board
        terms, exam format) for a node. A missing key resolves to ``None`` (no
        default invented)."""
        return {
            key: self.resolve(node_id, key, as_of=as_of)
            for key in HYPERLOCALIZATION_KEYS
        }


@dataclass(frozen=True)
class LocalizationConfig:
    """A flattened, plain hyperlocalization view for a node.

    Holds only the resolved VALUES for the surface to render. Any may be
    ``None`` — the module never invents a locale default; an unset value stays
    unset for the institution to choose. ``board_terms`` maps the platform's
    structural vocabulary to the institution's own words; ``exam_format`` is a
    board-agnostic descriptor of the local assessment pattern.
    """

    node_id: str
    language: Optional[str] = None
    region: Optional[str] = None
    calendar: Optional[str] = None
    board_terms: Optional[dict] = None
    exam_format: Optional[Any] = None

    @classmethod
    def from_policy_set(
        cls, policies: PolicySet, node_id: str, *, as_of: Optional[date] = None
    ) -> "LocalizationConfig":
        loc = policies.localization(node_id, as_of=as_of)

        def _val(key: str) -> Optional[Any]:
            rp = loc.get(key)
            return None if rp is None else rp.value

        return cls(
            node_id=node_id,
            language=_val(LOCALE_LANGUAGE),
            region=_val(LOCALE_REGION),
            calendar=_val(LOCALE_CALENDAR),
            board_terms=_val(LOCALE_BOARD_TERMS),
            exam_format=_val(LOCALE_EXAM_FORMAT),
        )

    def term_for(self, node_kind: str) -> Optional[str]:
        """The institution's own word for a structural ``node_kind`` (e.g.
        ``"grade" -> "Standard"``), or ``None`` if it uses the default."""
        if not self.board_terms:
            return None
        return self.board_terms.get(node_kind)
