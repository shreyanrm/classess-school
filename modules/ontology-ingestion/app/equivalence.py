"""Cross-board equivalence mapping (A2, Ring 1).

Maps a node in one board's ontology to the conceptually equivalent node in
another board's ontology, so a learner's evidence travels across boards without
the platform hard-coding any board. BOARD-AGNOSTIC by construction: every board
is a CODE label, never an enum of permitted boards; the SAME registry serves any
pair of boards and treats them identically.

Two properties the registry guarantees:
  - SYMMETRY. Equivalence is a symmetric relation: if board A's node ≡ board B's
    node, then board B's node ≡ board A's node, with the SAME confidence. The
    registry materialises the reverse mapping automatically, so a lookup from
    either side finds the other.
  - Explainability + confidence gate. Every mapping carries a confidence in
    [0,1] and a method label (how it was derived). Consumers gate on confidence;
    a low-confidence mapping is a candidate, not a trusted equivalence.

Equivalences may be proposed by the semantic index (similar curriculum text
across boards) and confirmed by a steward — but a proposal is never auto-trusted
(generate-and-verify). The registry tracks ``confirmed`` per mapping.

No PII: a mapping holds only opaque node ids, board CODE labels, and a label
string. Behavioural data never enters this module.

Import-safe: pure data structures, no I/O, no provider, no env read at import.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ._ontology import NodeKind


@dataclass(frozen=True)
class BoardNodeRef:
    """A reference to a node in a specific board's ontology.

    The board is a CODE label — never an enum. Two refs are equal iff their
    board code and node id match, so the registry can key on them.
    """

    board_code: str
    node_id: str
    node_kind: NodeKind
    label: str = ""  # human-readable, for explainability; not part of identity.

    def key(self) -> tuple[str, str]:
        return (self.board_code, self.node_id)


@dataclass(frozen=True)
class Equivalence:
    """A directed view of a symmetric equivalence between two board nodes.

    ``method`` records how the mapping was derived (e.g. ``steward``,
    ``semantic-index``) for explainability. ``confirmed`` is ``False`` for a
    proposal; a steward confirms it. The relation it represents is symmetric;
    the registry stores both directions so a lookup from either side succeeds.
    """

    left: BoardNodeRef
    right: BoardNodeRef
    confidence: float
    method: str = "steward"
    confirmed: bool = False

    def reversed(self) -> "Equivalence":
        """The symmetric counterpart — same confidence, swapped sides."""
        return replace(self, left=self.right, right=self.left)


class EquivalenceRegistry:
    """A symmetric, board-agnostic store of cross-board equivalences.

    Adding A≡B makes B≡A discoverable with the same confidence. Lookups by a
    node return its equivalents in ALL other boards. No board is privileged; the
    registry never special-cases a board code.
    """

    def __init__(self) -> None:
        # key: (board_code, node_id) -> list of directed equivalences FROM it.
        self._by_node: dict[tuple[str, str], list[Equivalence]] = {}
        # canonical undirected key -> the stored equivalence (one per pair).
        self._pairs: dict[tuple[tuple[str, str], tuple[str, str]], Equivalence] = {}

    @staticmethod
    def _pair_key(
        a: BoardNodeRef, b: BoardNodeRef
    ) -> tuple[tuple[str, str], tuple[str, str]]:
        """An order-independent key for an unordered pair of node refs, so A≡B
        and B≡A collapse to one stored pair (no duplicate, no asymmetry)."""
        ka, kb = a.key(), b.key()
        return (ka, kb) if ka <= kb else (kb, ka)

    def add(
        self,
        left: BoardNodeRef,
        right: BoardNodeRef,
        *,
        confidence: float,
        method: str = "steward",
        confirmed: bool = False,
    ) -> Equivalence:
        """Record a (possibly proposed) equivalence. Idempotent on the pair —
        re-adding the same pair updates it rather than duplicating. Refuses a
        self-equivalence (a node is trivially itself) and a same-board pairing
        across the SAME node (cross-board mapping is between distinct boards or
        distinct nodes)."""
        if left.key() == right.key():
            raise ValueError("A node cannot be cross-mapped to itself.")
        confidence = max(0.0, min(1.0, float(confidence)))
        equivalence = Equivalence(
            left=left, right=right, confidence=confidence, method=method, confirmed=confirmed
        )
        pair_key = self._pair_key(left, right)
        self._pairs[pair_key] = equivalence
        self._reindex()
        return equivalence

    def propose(
        self,
        left: BoardNodeRef,
        right: BoardNodeRef,
        *,
        confidence: float,
        method: str = "semantic-index",
    ) -> Equivalence:
        """Propose an UNCONFIRMED equivalence (generate-and-verify). Never
        trusted until :meth:`confirm`."""
        return self.add(left, right, confidence=confidence, method=method, confirmed=False)

    def confirm(self, left: BoardNodeRef, right: BoardNodeRef) -> Equivalence:
        """Mark a stored equivalence confirmed by a steward. Raises if unknown."""
        pair_key = self._pair_key(left, right)
        current = self._pairs.get(pair_key)
        if current is None:
            raise KeyError("No such equivalence to confirm.")
        confirmed = replace(current, confirmed=True)
        self._pairs[pair_key] = confirmed
        self._reindex()
        return confirmed

    def _reindex(self) -> None:
        """Rebuild the per-node directed view from the canonical pairs, BOTH
        directions — this is where symmetry is materialised."""
        self._by_node = {}
        for equivalence in self._pairs.values():
            forward = equivalence
            backward = equivalence.reversed()
            self._by_node.setdefault(forward.left.key(), []).append(forward)
            self._by_node.setdefault(backward.left.key(), []).append(backward)

    def equivalents_of(
        self, ref: BoardNodeRef, *, min_confidence: float = 0.0, confirmed_only: bool = False
    ) -> list[Equivalence]:
        """All equivalences FROM ``ref`` to nodes in other boards.

        ``min_confidence`` applies the confidence gate; ``confirmed_only``
        filters to steward-confirmed mappings (the trusted set for routing)."""
        results = self._by_node.get(ref.key(), [])
        out = [
            e
            for e in results
            if e.confidence >= min_confidence and (e.confirmed or not confirmed_only)
        ]
        return sorted(out, key=lambda e: e.confidence, reverse=True)

    def are_equivalent(
        self, a: BoardNodeRef, b: BoardNodeRef, *, confirmed_only: bool = False
    ) -> bool:
        """True iff a and b are mapped equivalent (symmetric — order-free)."""
        equivalence = self._pairs.get(self._pair_key(a, b))
        if equivalence is None:
            return False
        return equivalence.confirmed or not confirmed_only

    def all(self) -> list[Equivalence]:
        """All canonical (deduplicated) equivalences."""
        return list(self._pairs.values())

    def board_codes(self) -> set[str]:
        """Every board code present — proof the registry is data-driven, never a
        fixed board set."""
        codes: set[str] = set()
        for equivalence in self._pairs.values():
            codes.add(equivalence.left.board_code)
            codes.add(equivalence.right.board_code)
        return codes

    def __len__(self) -> int:
        return len(self._pairs)
