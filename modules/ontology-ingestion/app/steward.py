"""The prerequisite-edge steward (A2, Ring 1).

Prerequisite edges (topic → topic) are an OWNED, expert-validated artifact. The
steward PROPOSES edges; a human expert CONFIRMS them before they are trusted for
routing. This is the central law of A2: a proposed edge is NEVER auto-trusted.

What the steward does:
  - Proposes candidate prerequisite edges from evidence — sequence order within
    a chapter, and (when a semantic index is supplied) curriculum-text
    similarity between topics. Every proposal carries a rationale and a
    confidence (explainability + the confidence gate).
  - Holds proposals as ``confirmed = False``. ``trusted_edges()`` returns only
    edges a steward has confirmed — the routing-safe set.
  - Confirms / rejects on an EXPLICIT human steward decision (an opaque steward
    ref). The steward object never confirms an edge on its own — confirmation is
    a consequential act on the permission ladder and requires a human ref.

Generate-and-verify with a confidence gate: a proposal below the gate is still
recorded (for the reviewer) but flagged low-confidence; nothing crosses into the
trusted set without human confirmation regardless of confidence.

No PII: edges hold only opaque topic ids, kinds, rationales, and an opaque
steward ref on confirmation. Behavioural data never enters this module.

Import-safe: pure logic over the in-memory snapshot + an optional semantic
index. No I/O, no provider, no env read at import.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Optional

from ._ontology import Edge, OntologySnapshot, PrerequisiteKind, Topic
from .embeddings import SemanticIndex, SimilarityHit


# Confidence the steward attaches to a same-chapter sequence-adjacency proposal.
SEQUENCE_PROPOSAL_CONFIDENCE = 0.55
# Minimum cosine similarity for a semantic cross-topic proposal to be raised.
SEMANTIC_SIMILARITY_THRESHOLD = 0.45
# The confidence gate: a proposal at/above this is "review-ready"; below it is
# flagged low-confidence. NOTHING is trusted on confidence alone — only on
# human confirmation.
DEFAULT_CONFIDENCE_GATE = 0.6


def _new_edge_id() -> str:
    return str(uuid.uuid4())


@dataclass
class ProposedEdge:
    """A steward proposal for a prerequisite edge.

    Wraps the contract :class:`Edge` (always ``confirmed = False`` while
    proposed) with the steward's confidence, the evidence method, and a
    review flag. ``below_gate`` marks a proposal under the confidence gate.
    """

    edge: Edge
    confidence: float
    method: str          # "sequence" | "semantic" | "manual"
    below_gate: bool

    @property
    def id(self) -> str:
        return self.edge.id

    @property
    def confirmed(self) -> bool:
        return self.edge.confirmed  # always False while a proposal.


@dataclass
class StewardDecision:
    """The record of a human steward's decision on a proposed edge."""

    edge_id: str
    decision: str        # "confirmed" | "rejected"
    steward_ref: str     # opaque human ref — never a name.


class PrerequisiteSteward:
    """Proposes prerequisite edges and tracks human confirmation.

    Construct over an ontology snapshot. Call :meth:`propose_from_snapshot` (and
    optionally pass a :class:`SemanticIndex` for similarity-based proposals) to
    generate candidates. Edges only enter the trusted set via :meth:`confirm`,
    which requires an explicit human steward ref.
    """

    def __init__(
        self,
        snapshot: OntologySnapshot,
        *,
        confidence_gate: float = DEFAULT_CONFIDENCE_GATE,
    ) -> None:
        self._snapshot = snapshot
        self._gate = confidence_gate
        # edge_id -> ProposedEdge (current state; confirmation mutates a copy).
        self._proposals: dict[str, ProposedEdge] = {}
        self._decisions: list[StewardDecision] = []
        # Seed from any edges already on the snapshot, preserving their
        # confirmed flag (the seed ontology ships some confirmed, one proposed).
        for edge in snapshot.edges:
            self._proposals[edge.id] = ProposedEdge(
                edge=edge,
                confidence=1.0 if edge.confirmed else SEQUENCE_PROPOSAL_CONFIDENCE,
                method="seed",
                below_gate=False,
            )

    # -- proposal ----------------------------------------------------------

    def propose(
        self,
        *,
        from_topic_id: str,
        to_topic_id: str,
        kind: PrerequisiteKind,
        rationale: str,
        confidence: float,
        method: str = "manual",
    ) -> ProposedEdge:
        """Raise a single proposed edge. Always ``confirmed = False`` — never
        trusted until a steward confirms it. Refuses a self-edge and a pair of
        topics not both in the snapshot."""
        if from_topic_id == to_topic_id:
            raise ValueError("A topic cannot be its own prerequisite.")
        topic_ids = self._snapshot.topic_ids()
        if from_topic_id not in topic_ids or to_topic_id not in topic_ids:
            raise ValueError("Both topics must exist in the ontology snapshot.")
        confidence = max(0.0, min(1.0, float(confidence)))
        edge = Edge(
            id=_new_edge_id(),
            from_topic_id=from_topic_id,
            to_topic_id=to_topic_id,
            kind=kind,
            confirmed=False,  # LAW: a proposal is never auto-trusted.
            rationale=rationale,
        )
        proposal = ProposedEdge(
            edge=edge,
            confidence=confidence,
            method=method,
            below_gate=confidence < self._gate,
        )
        self._proposals[edge.id] = proposal
        return proposal

    def propose_from_snapshot(
        self, *, semantic_index: Optional[SemanticIndex] = None
    ) -> list[ProposedEdge]:
        """Generate candidate edges from the snapshot's evidence.

        Two heuristics, both producing UNCONFIRMED proposals:
          1. Sequence adjacency within a chapter — topic N is a soft prerequisite
             of topic N+1 (curriculum order is weak evidence of dependency).
          2. Semantic similarity (when a :class:`SemanticIndex` is supplied) —
             two topics with similar curriculum text MAY be related; raised as a
             soft proposal for the steward to judge.

        Never returns trusted edges; every proposal needs human confirmation.
        Skips pairs already proposed/confirmed (idempotent).
        """
        new_proposals: list[ProposedEdge] = []
        new_proposals.extend(self._propose_sequence_edges())
        if semantic_index is not None:
            new_proposals.extend(self._propose_semantic_edges(semantic_index))
        return new_proposals

    def _existing_pairs(self) -> set[tuple[str, str]]:
        return {(p.edge.from_topic_id, p.edge.to_topic_id) for p in self._proposals.values()}

    def _propose_sequence_edges(self) -> list[ProposedEdge]:
        existing = self._existing_pairs()
        # Group topics by chapter, ordered by sequence.
        by_chapter: dict[str, list[Topic]] = {}
        for topic in self._snapshot.topics:
            by_chapter.setdefault(topic.chapter_id, []).append(topic)
        out: list[ProposedEdge] = []
        for topics in by_chapter.values():
            topics_sorted = sorted(topics, key=lambda t: t.sequence)
            for earlier, later in zip(topics_sorted, topics_sorted[1:]):
                pair = (earlier.id, later.id)
                if pair in existing:
                    continue
                proposal = self.propose(
                    from_topic_id=earlier.id,
                    to_topic_id=later.id,
                    kind=PrerequisiteKind.SOFT,
                    rationale=(
                        f"Proposed from curriculum order: '{earlier.name}' precedes "
                        f"'{later.name}' in the same chapter. Awaiting steward "
                        "confirmation before it is trusted for routing."
                    ),
                    confidence=SEQUENCE_PROPOSAL_CONFIDENCE,
                    method="sequence",
                )
                existing.add(pair)
                out.append(proposal)
        return out

    def _propose_semantic_edges(self, semantic_index: SemanticIndex) -> list[ProposedEdge]:
        existing = self._existing_pairs()
        out: list[ProposedEdge] = []
        topics = self._snapshot.topics
        for topic in topics:
            hits: list[SimilarityHit] = semantic_index.similar_to_text(
                topic.name, top_k=4
            )
            for hit in hits:
                if hit.node_id == topic.id:
                    continue  # self.
                if hit.score < SEMANTIC_SIMILARITY_THRESHOLD:
                    continue
                # Direct: the earlier-sequenced topic is the prerequisite.
                other = self._snapshot.topic_by_id(hit.node_id)
                if other is None:
                    continue
                earlier, later = self._order_by_sequence(topic, other)
                pair = (earlier.id, later.id)
                if pair in existing:
                    continue
                proposal = self.propose(
                    from_topic_id=earlier.id,
                    to_topic_id=later.id,
                    kind=PrerequisiteKind.SOFT,
                    rationale=(
                        f"Proposed from curriculum-text similarity (score "
                        f"{hit.score:.2f}) between '{earlier.name}' and "
                        f"'{later.name}'. A candidate only — awaiting steward "
                        "confirmation."
                    ),
                    confidence=round(min(0.59, hit.score), 4),
                    method="semantic",
                )
                existing.add(pair)
                out.append(proposal)
        return out

    @staticmethod
    def _order_by_sequence(a: Topic, b: Topic) -> tuple[Topic, Topic]:
        """Order two topics so the earlier-sequenced is the prerequisite. Stable
        on id when sequences tie, so proposals are deterministic."""
        ka = (a.sequence, a.id)
        kb = (b.sequence, b.id)
        return (a, b) if ka <= kb else (b, a)

    # -- confirmation (human, consequential) -------------------------------

    def confirm(self, edge_id: str, *, steward_ref: str) -> Edge:
        """Confirm a proposed edge — trusts it for routing.

        Requires an explicit opaque ``steward_ref`` (a human expert). The
        steward object NEVER confirms an edge on its own: confirming a
        prerequisite is consequential and sits on the permission ladder. Refuses
        without a steward ref."""
        if not steward_ref:
            raise PermissionError(
                "Confirming a prerequisite edge is a consequential expert act "
                "and requires a steward_ref. Edges are never auto-confirmed."
            )
        proposal = self._proposals.get(edge_id)
        if proposal is None:
            raise KeyError(f"No proposed edge with id {edge_id}.")
        confirmed_edge = replace(proposal.edge, confirmed=True)
        self._proposals[edge_id] = replace(proposal, edge=confirmed_edge)
        self._decisions.append(
            StewardDecision(edge_id=edge_id, decision="confirmed", steward_ref=steward_ref)
        )
        return confirmed_edge

    def reject(self, edge_id: str, *, steward_ref: str) -> None:
        """Reject a proposed edge — removes it from the candidate set.

        Requires a steward ref (a human decision, recorded append-only)."""
        if not steward_ref:
            raise PermissionError(
                "Rejecting a prerequisite edge is an expert decision and "
                "requires a steward_ref."
            )
        if edge_id not in self._proposals:
            raise KeyError(f"No proposed edge with id {edge_id}.")
        del self._proposals[edge_id]
        self._decisions.append(
            StewardDecision(edge_id=edge_id, decision="rejected", steward_ref=steward_ref)
        )

    # -- views -------------------------------------------------------------

    def proposals(self) -> list[ProposedEdge]:
        """All current proposals (confirmed and unconfirmed)."""
        return list(self._proposals.values())

    def pending(self) -> list[ProposedEdge]:
        """Proposals awaiting a steward decision (the review queue)."""
        return [p for p in self._proposals.values() if not p.edge.confirmed]

    def trusted_edges(self) -> list[Edge]:
        """The routing-safe set: ONLY steward-confirmed edges. This is the law
        — a consumer routing on prerequisites uses this, never raw proposals."""
        return [p.edge for p in self._proposals.values() if p.edge.confirmed]

    def decisions(self) -> list[StewardDecision]:
        """The append-only log of steward decisions."""
        return list(self._decisions)
