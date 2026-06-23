"""Competitive-exam mappings + school-defined local overlays (A2, Ring 1).

The ontology holds more than one board's curriculum: it also maps nodes to
COMPETITIVE-EXAM syllabi and carries SCHOOL-DEFINED LOCAL OVERLAYS — both as
projections OVER the shared graph, never as mutations of it.

  - Competitive-exam mappings. A node (topic / outcome) may also be examined by
    a competitive exam. The exam is a CODE label (board-agnostic in the same
    spirit — no exam is baked in). Mappings carry a confidence + a ``confirmed``
    flag: a proposed mapping is a candidate, never auto-trusted (generate-and-
    verify, human final). The registry filters by exam, by confidence gate, and
    by confirmed-only (the trusted set).
  - Local overlays. A school adds local context — an alias, a re-sequence, an
    emphasis flag, a note, a hidden flag — keyed by an opaque ``scope_ref``
    (tenant/school). The base graph is IDENTICAL for everyone; the overlay is
    applied as a per-scope projection. The base node is never edited, so a
    school's local view never leaks into another's.

No PII: mappings + overlays hold only opaque ids, neutral labels, and an opaque
scope ref. Behavioural data never enters this module.

Import-safe: pure data structures + read projections. No I/O, no provider, no
env read at import.
"""

from __future__ import annotations

from dataclasses import dataclass

from ._ontology import (
    CompetitiveExamMapping,
    LocalOverlay,
    NodeKind,
    OntologySnapshot,
)


# ---------------------------------------------------------------------------
# Competitive-exam mappings
# ---------------------------------------------------------------------------


class CompetitiveExamRegistry:
    """A read view over a snapshot's competitive-exam mappings.

    Board-agnostic over exams: the exam is a CODE label and the registry never
    special-cases one. A proposed mapping is never trusted until confirmed.
    """

    def __init__(self, snapshot: OntologySnapshot) -> None:
        self._mappings = list(snapshot.exam_mappings)

    def exam_codes(self) -> set[str]:
        """Every exam code present — proof the set is data-driven, not fixed."""
        return {m.exam_code for m in self._mappings}

    def for_node(
        self,
        node_id: str,
        *,
        min_confidence: float = 0.0,
        confirmed_only: bool = False,
    ) -> list[CompetitiveExamMapping]:
        """Exam mappings for one node, highest-confidence first.

        ``min_confidence`` applies the confidence gate; ``confirmed_only`` keeps
        only steward-confirmed mappings (the trusted set)."""
        out = [
            m
            for m in self._mappings
            if m.node_id == node_id
            and m.confidence >= min_confidence
            and (m.confirmed or not confirmed_only)
        ]
        return sorted(out, key=lambda m: m.confidence, reverse=True)

    def for_exam(
        self,
        exam_code: str,
        *,
        min_confidence: float = 0.0,
        confirmed_only: bool = False,
    ) -> list[CompetitiveExamMapping]:
        """Every node mapped to one exam, highest-weight first (then confidence).
        The trusted set for that exam when ``confirmed_only`` is set."""
        out = [
            m
            for m in self._mappings
            if m.exam_code == exam_code
            and m.confidence >= min_confidence
            and (m.confirmed or not confirmed_only)
        ]
        return sorted(out, key=lambda m: (m.weight, m.confidence), reverse=True)

    def pending(self) -> list[CompetitiveExamMapping]:
        """Proposed (unconfirmed) mappings — the steward review queue."""
        return [m for m in self._mappings if not m.confirmed]


# ---------------------------------------------------------------------------
# School-defined local overlays
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OverlayedNode:
    """The per-scope projection of one node after overlays are applied.

    ``label`` is the alias (or the base label when no alias). ``emphasis`` /
    ``hidden`` / ``sequence`` / ``notes`` capture the other overlay kinds. The
    base node is untouched — this is a derived view for ONE scope only.
    """

    node_id: str
    node_kind: NodeKind
    label: str
    emphasis: str | None = None
    hidden: bool = False
    sequence: int | None = None
    notes: tuple[str, ...] = ()


class LocalOverlayProjection:
    """Applies a single scope's local overlays over the base graph.

    Construct with a snapshot and an opaque ``scope_ref``; the projection reads
    ONLY that scope's overlays, so one school's local view never bleeds into
    another's. The base snapshot is never mutated.
    """

    def __init__(self, snapshot: OntologySnapshot, *, scope_ref: str) -> None:
        self._snapshot = snapshot
        self._scope_ref = scope_ref
        self._overlays = [o for o in snapshot.overlays if o.scope_ref == scope_ref]
        self._base_labels = self._index_base_labels(snapshot)

    @staticmethod
    def _index_base_labels(snapshot: OntologySnapshot) -> dict[str, tuple[NodeKind, str]]:
        index: dict[str, tuple[NodeKind, str]] = {}
        index[snapshot.board.id] = (NodeKind.BOARD, snapshot.board.name)
        for g in snapshot.grades:
            index[g.id] = (NodeKind.GRADE, g.name)
        for s in snapshot.subjects:
            index[s.id] = (NodeKind.SUBJECT, s.name)
        for u in snapshot.units:
            index[u.id] = (NodeKind.UNIT, u.name)
        for c in snapshot.chapters:
            index[c.id] = (NodeKind.CHAPTER, c.name)
        for t in snapshot.topics:
            index[t.id] = (NodeKind.TOPIC, t.name)
        for o in snapshot.outcomes:
            index[o.id] = (NodeKind.OUTCOME, o.statement)
        for cp in snapshot.competencies:
            index[cp.id] = (NodeKind.COMPETENCY, cp.name)
        for sk in snapshot.skills:
            index[sk.id] = (NodeKind.SKILL, sk.name)
        return index

    def overlays_for(self, node_id: str) -> list[LocalOverlay]:
        """This scope's overlays on one node."""
        return [o for o in self._overlays if o.node_id == node_id]

    def project(self, node_id: str) -> OverlayedNode | None:
        """The overlayed view of one node for this scope, or ``None`` if the
        base node is unknown. With no overlays the projection equals the base."""
        base = self._base_labels.get(node_id)
        if base is None:
            return None
        kind, base_label = base
        label = base_label
        emphasis: str | None = None
        hidden = False
        sequence: int | None = None
        notes: list[str] = []
        for overlay in self.overlays_for(node_id):
            if overlay.overlay_kind == "alias":
                label = overlay.value
            elif overlay.overlay_kind == "emphasis":
                emphasis = overlay.value
            elif overlay.overlay_kind == "hidden":
                hidden = overlay.value.lower() in {"1", "true", "yes", "hidden"}
            elif overlay.overlay_kind == "resequence":
                try:
                    sequence = int(overlay.value)
                except ValueError:
                    sequence = None
            elif overlay.overlay_kind == "note":
                notes.append(overlay.value)
        return OverlayedNode(
            node_id=node_id,
            node_kind=kind,
            label=label,
            emphasis=emphasis,
            hidden=hidden,
            sequence=sequence,
            notes=tuple(notes),
        )

    def scope_ref(self) -> str:
        return self._scope_ref
