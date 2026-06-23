"""Curriculum ingestion (A2, Ring 1).

Ingests curriculum from documents / standards / publisher content INTO the
ontology graph. The output is a set of DRAFT ontology nodes
(board → grade → subject → unit → chapter → topic → outcome) placed under their
parents — never hard-coded to a board, and never trusted until reviewed.

The document-understanding step is an INTERFACE that degrades gracefully:

  - :class:`DocumentUnderstanding` — a Protocol that turns a source document
    into a structured curriculum OUTLINE (a tree of titled sections). The live
    implementation calls a provider THROUGH the gateway; its key is NAMED in
    config, never read for a value here and never hardcoded.
  - :class:`NullDocumentUnderstanding` — the offline default. It does NOT invent
    structure: it reports unavailable and ingestion falls back to a
    STRUCTURED-SOURCE path (publisher / standards content already shaped as an
    outline) or records the artefact as pending extraction. It never fabricates
    OCR / understanding output.

Two laws bind ingestion:
  - Generate-and-verify with a confidence gate: extracted nodes are DRAFTS. A
    node below the confidence gate is flagged ``needs_review`` and never silently
    trusted. Promotion to a trusted node is a separate, human act (the steward /
    a reviewer), exactly as prerequisite edges are.
  - Board-agnostic: the board is taken from the source as a labelled node. No
    board name is baked into the code; the SAME pipeline ingests any board.

No learner PII lives on an ontology node — nodes carry only opaque ids, kinds,
names, and statements (INVARIANT: behavioural data carries only canonical_uuid;
ontology metadata carries none). The source is recorded as an opaque handle.

Import-safe: importing this module performs no I/O, reads no secret value, and
requires no live provider.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol, Sequence, runtime_checkable

from ._ontology import (
    Board,
    Chapter,
    Competency,
    Edge,
    Grade,
    NodeKind,
    OntologySnapshot,
    Outcome,
    Subject,
    Topic,
    Unit,
)
from .config import ENV_DOC_UNDERSTANDING_KEY, OntologySettings, get_settings
from .gemini import GeminiDocumentUnderstanding, ProposedEdgeHint


# Default confidence gate. A node understood below this is flagged needs_review
# rather than trusted. Generate-and-verify: nothing crosses the gate silently.
DEFAULT_CONFIDENCE_GATE = 0.6


# ---------------------------------------------------------------------------
# Source + understanding shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutlineNode:
    """One node in a parsed curriculum outline.

    ``kind`` is an ontology :class:`NodeKind` value; ``children`` are the nodes
    one level finer. ``statement`` carries an outcome's can-do text. This is the
    board-agnostic intermediate shape both the live provider and the
    structured-source path produce, so ingestion maps a single shape.
    """

    kind: NodeKind
    title: str
    confidence: float = 1.0
    statement: str | None = None  # for outcomes — the observable can-do text.
    sequence: int = 0
    children: tuple["OutlineNode", ...] = ()


@dataclass(frozen=True)
class SourceDocument:
    """A document / standard / publisher artefact to ingest.

    ``source_ref`` is an opaque handle (e.g. a content-store id), NOT the bytes.
    ``board_code`` / ``board_name`` are LABELS read from the source — the board
    is data, never a baked-in option. ``raw_outline`` is set when the source is
    already structured (publisher / standards feed); when absent the document
    understanding provider is asked to produce one.
    """

    source_ref: str
    board_code: str
    board_name: str
    region: str | None = None
    raw_outline: tuple[OutlineNode, ...] = ()
    # The document body (plain text / markdown / extracted PDF text) handed to
    # the live Gemini understanding path. Opaque content, never PII about a
    # learner. When ``raw_outline`` is present it wins; this feeds the model.
    document_text: str | None = None


@runtime_checkable
class DocumentUnderstanding(Protocol):
    """Turns an unstructured source into a curriculum outline.

    The live implementation calls a document-understanding provider THROUGH the
    gateway (key read from the environment by NAME at the egress point, never
    here). Implementations must NOT invent structure when they cannot read the
    source — return ``available = False`` instead.
    """

    def understand(self, document: SourceDocument) -> "UnderstandingResult": ...


@dataclass(frozen=True)
class UnderstandingResult:
    """The outcome of a document-understanding step.

    ``proposed_edges`` are PROPOSED prerequisite hints (by topic title) the live
    path may surface. They are candidates only — the steward holds them
    UNCONFIRMED until a human confirms them; ingestion never trusts them.
    """

    outline: tuple[OutlineNode, ...]
    available: bool       # False when no provider ran (degraded path).
    provider: str         # provider label or "none".
    detail: str | None = None
    proposed_edges: tuple[ProposedEdgeHint, ...] = ()


class NullDocumentUnderstanding:
    """The offline default. Never invents structure.

    Reports unavailable so ingestion uses the structured-source path
    (``SourceDocument.raw_outline``) when present, or records pending extraction
    when not. This is the supported path until a provider is wired.
    """

    provider = "none"

    def understand(self, document: SourceDocument) -> UnderstandingResult:
        return UnderstandingResult(
            outline=(),
            available=False,
            provider=self.provider,
            detail=(
                "No document-understanding provider configured. Set "
                f"{ENV_DOC_UNDERSTANDING_KEY} (read at the gateway egress, by "
                "NAME) to enable extraction, or supply a structured raw_outline."
            ),
        )


def _outline_node_from_dict(node: dict) -> OutlineNode:
    """Map one cleaned Gemini outline dict onto an :class:`OutlineNode`.

    ``kind`` was validated by the Gemini parser to be an ontology level, so the
    lookup is total here. Recurses into children. Pure — no I/O.
    """
    children = tuple(_outline_node_from_dict(c) for c in node.get("children", []))
    return OutlineNode(
        kind=NodeKind(node["kind"]),
        title=node["title"],
        confidence=float(node.get("confidence", 1.0)),
        statement=node.get("statement"),
        sequence=int(node.get("sequence", 0)),
        children=children,
    )


class GeminiUnderstandingAdapter:
    """Adapts the real :class:`GeminiDocumentUnderstanding` to the Protocol.

    Turns the provider's cleaned outline dicts into :class:`OutlineNode` trees
    and carries proposed prerequisite hints. Degrades exactly as the client does
    — an unavailable extraction yields an unavailable result with no invention.
    """

    def __init__(self, client: GeminiDocumentUnderstanding) -> None:
        self._client = client

    @property
    def provider(self) -> str:
        return self._client.provider

    def understand(self, document: SourceDocument) -> UnderstandingResult:
        extraction = self._client.extract(
            document.document_text or "", board_name=document.board_name
        )
        outline = tuple(_outline_node_from_dict(n) for n in extraction.outline)
        return UnderstandingResult(
            outline=outline,
            available=extraction.available,
            provider=extraction.provider,
            detail=extraction.detail,
            proposed_edges=tuple(extraction.edge_hints),
        )


def default_document_understanding(
    settings: OntologySettings | None = None,
) -> DocumentUnderstanding:
    """Select the document-understanding implementation.

    Precedence:
      1. The REAL Gemini path when a Gemini key is set (``has_gemini``). It reads
         the key by NAME at egress and degrades cleanly per-call when the call
         fails — so it is always safe to construct, even offline.
      2. The gateway-routed provider seam when ``has_doc_understanding`` is set
         but no Gemini key is — intentionally not wired (the Protocol is the
         contract); this stays a clear error rather than a silent fabrication.
      3. The Null provider otherwise (the degraded, deterministic path).
    """
    settings = settings or get_settings()
    if settings.has_gemini:
        return GeminiUnderstandingAdapter(GeminiDocumentUnderstanding(settings=settings))
    if not settings.has_doc_understanding:
        return NullDocumentUnderstanding()
    raise NotImplementedError(
        "A gateway-routed document-understanding provider is configured but not "
        "wired. Implement a DocumentUnderstanding that calls the provider "
        f"through the gateway (token + {ENV_DOC_UNDERSTANDING_KEY} read from the "
        "environment by NAME), or set the Gemini key for the real direct path. "
        "Until then leave the provider key unset to use the Null provider with "
        "the structured-source path."
    )


# ---------------------------------------------------------------------------
# Ingestion result
# ---------------------------------------------------------------------------


@dataclass
class IngestedNode:
    """A single node produced by ingestion, with its review status."""

    node_id: str
    kind: NodeKind
    title: str
    confidence: float
    needs_review: bool   # True when below the confidence gate (generate-verify).
    parent_id: str | None


@dataclass
class IngestResult:
    """The result of ingesting one source document.

    ``snapshot`` is a DRAFT ontology snapshot built from the outline — every
    node placed under its parent in the contract chain. ``nodes`` is the flat
    review list with confidence + needs_review. ``available`` reflects whether
    real understanding ran. Nothing here is trusted until reviewed.
    """

    snapshot: OntologySnapshot
    nodes: list[IngestedNode] = field(default_factory=list)
    available: bool = False
    provider: str = "none"
    pending_extraction: bool = False
    detail: str | None = None
    # PROPOSED prerequisite edges resolved from the live path's hints. Each is
    # placed on ``snapshot.edges`` with ``confirmed = False`` — UNCONFIRMED until
    # a human steward confirms it. Surfaced here for the review queue.
    proposed_edges: list[Edge] = field(default_factory=list)

    @property
    def needs_review(self) -> list[IngestedNode]:
        return [n for n in self.nodes if n.needs_review]

    @property
    def draft(self) -> bool:
        """Ingested nodes are ALWAYS drafts — promotion is a separate human act."""
        return True

    @property
    def has_unconfirmed_edges(self) -> bool:
        """True when any proposed edge is awaiting steward confirmation. Every
        proposed edge is unconfirmed by construction — there is no auto-trust."""
        return any(not e.confirmed for e in self.proposed_edges)


# ---------------------------------------------------------------------------
# Deterministic id derivation (opaque, stable, PII-free)
# ---------------------------------------------------------------------------


def _derive_id(board_code: str, *parts: str) -> str:
    """Derive a stable opaque UUID-shaped id from board + path parts.

    Deterministic so re-ingesting the same source maps to the same node id
    (idempotent ingestion). Pure hashing — no PII, no randomness, no network.
    """
    seed = "::".join([board_code, *parts])
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    # Shape as a UUIDv4-looking string (version nibble 4, variant 8).
    return f"{digest[0:8]}-{digest[8:12]}-4{digest[13:16]}-8{digest[17:20]}-{digest[20:32]}"


# ---------------------------------------------------------------------------
# The ingester
# ---------------------------------------------------------------------------


class CurriculumIngester:
    """Maps a source document into a DRAFT ontology snapshot.

    Walks the curriculum outline (from the live provider, or the structured
    source, or — failing both — none) and places each node under its parent in
    the board → … → outcome chain. Applies the confidence gate: a node below the
    gate is flagged ``needs_review``. Board-agnostic by construction — the board
    is read from the source as a label.
    """

    def __init__(
        self,
        *,
        understanding: DocumentUnderstanding | None = None,
        settings: OntologySettings | None = None,
        confidence_gate: float = DEFAULT_CONFIDENCE_GATE,
    ) -> None:
        self._settings = settings or get_settings()
        self._understanding = understanding or default_document_understanding(self._settings)
        self._gate = confidence_gate

    @property
    def degraded(self) -> bool:
        """Degraded when NO live understanding path is configured (neither the
        real Gemini key nor the gateway-routed provider)."""
        return not (self._settings.has_gemini or self._settings.has_doc_understanding)

    def ingest(self, document: SourceDocument) -> IngestResult:
        """Ingest one document into a DRAFT ontology snapshot."""
        board = Board(
            id=_derive_id(document.board_code, "board"),
            code=document.board_code,
            name=document.board_name,
            region=document.region,
        )
        snapshot = OntologySnapshot(board=board)

        # Choose the outline source. Structured source wins when present (it is
        # already trusted shape); otherwise ask the provider; never invent.
        outline: Sequence[OutlineNode]
        available: bool
        provider: str
        detail: str | None
        edge_hints: tuple[ProposedEdgeHint, ...] = ()
        if document.raw_outline:
            outline = document.raw_outline
            available = True
            provider = "structured-source"
            detail = "Ingested from a structured publisher/standards outline."
        else:
            result = self._understanding.understand(document)
            outline = result.outline
            available = result.available
            provider = result.provider
            detail = result.detail
            edge_hints = result.proposed_edges

        nodes: list[IngestedNode] = []
        if not outline:
            # No structure available — record pending extraction, no invention.
            return IngestResult(
                snapshot=snapshot,
                nodes=nodes,
                available=available,
                provider=provider,
                pending_extraction=True,
                detail=detail or "No curriculum structure available to ingest.",
            )

        for child in outline:
            self._walk(document.board_code, child, parent_id=board.id, snapshot=snapshot, nodes=nodes)

        # Resolve any proposed prerequisite hints (by topic title) into
        # UNCONFIRMED edges on the snapshot. Every one starts confirmed=False —
        # a proposal is never auto-trusted; the steward holds it for review.
        proposed_edges = self._resolve_edge_hints(
            document.board_code, edge_hints, snapshot
        )
        snapshot.edges.extend(proposed_edges)

        return IngestResult(
            snapshot=snapshot,
            nodes=nodes,
            available=available,
            provider=provider,
            pending_extraction=False,
            detail=detail,
            proposed_edges=proposed_edges,
        )

    def _resolve_edge_hints(
        self,
        board_code: str,
        hints: tuple[ProposedEdgeHint, ...],
        snapshot: OntologySnapshot,
    ) -> list[Edge]:
        """Map title-based prerequisite hints onto UNCONFIRMED topic→topic edges.

        Resolves each hint's titles to the topic ids just placed on the snapshot
        (case-insensitive). Drops a hint whose titles do not both resolve to
        distinct topics — never invents a topic to satisfy an edge. Every edge is
        ``confirmed = False`` (a proposal is never auto-trusted) with a
        deterministic, idempotent id derived from the board + topic pair.
        """
        if not hints:
            return []
        by_title: dict[str, str] = {}
        for topic in snapshot.topics:
            by_title.setdefault(topic.name.strip().lower(), topic.id)
        edges: list[Edge] = []
        seen: set[tuple[str, str]] = set()
        for hint in hints:
            frm_id = by_title.get(hint.from_title.strip().lower())
            to_id = by_title.get(hint.to_title.strip().lower())
            if frm_id is None or to_id is None or frm_id == to_id:
                continue
            pair = (frm_id, to_id)
            if pair in seen:
                continue
            seen.add(pair)
            edges.append(
                Edge(
                    id=_derive_id(board_code, "edge", frm_id, to_id),
                    from_topic_id=frm_id,
                    to_topic_id=to_id,
                    kind=hint.kind,
                    confirmed=False,  # LAW: proposed edges are never auto-trusted.
                    rationale=hint.rationale,
                )
            )
        return edges

    # -- internals ---------------------------------------------------------

    def _walk(
        self,
        board_code: str,
        node: OutlineNode,
        *,
        parent_id: str,
        snapshot: OntologySnapshot,
        nodes: list[IngestedNode],
        path: tuple[str, ...] = (),
    ) -> None:
        node_path = (*path, f"{node.kind.value}:{node.title}")
        node_id = _derive_id(board_code, *node_path)
        needs_review = node.confidence < self._gate
        self._attach(node, node_id=node_id, parent_id=parent_id, snapshot=snapshot)
        nodes.append(
            IngestedNode(
                node_id=node_id,
                kind=node.kind,
                title=node.title,
                confidence=node.confidence,
                needs_review=needs_review,
                parent_id=parent_id,
            )
        )
        for child in node.children:
            self._walk(
                board_code,
                child,
                parent_id=node_id,
                snapshot=snapshot,
                nodes=nodes,
                path=node_path,
            )

    def _attach(
        self,
        node: OutlineNode,
        *,
        node_id: str,
        parent_id: str,
        snapshot: OntologySnapshot,
    ) -> None:
        """Map one outline node onto the correct typed ontology table."""
        kind = node.kind
        if kind is NodeKind.GRADE:
            level = _grade_level(node.title)
            snapshot.grades.append(
                Grade(id=node_id, board_id=parent_id, level=level, name=node.title)
            )
        elif kind is NodeKind.SUBJECT:
            snapshot.subjects.append(
                Subject(id=node_id, grade_id=parent_id, name=node.title)
            )
        elif kind is NodeKind.UNIT:
            snapshot.units.append(
                Unit(id=node_id, subject_id=parent_id, name=node.title, sequence=node.sequence)
            )
        elif kind is NodeKind.CHAPTER:
            snapshot.chapters.append(
                Chapter(id=node_id, unit_id=parent_id, name=node.title, sequence=node.sequence)
            )
        elif kind is NodeKind.TOPIC:
            snapshot.topics.append(
                Topic(id=node_id, chapter_id=parent_id, name=node.title, sequence=node.sequence)
            )
        elif kind is NodeKind.OUTCOME:
            statement = node.statement or node.title
            snapshot.outcomes.append(
                Outcome(id=node_id, topic_id=parent_id, statement=statement)
            )
        elif kind is NodeKind.COMPETENCY:
            snapshot.competencies.append(
                Competency(
                    id=node_id,
                    subject_id=parent_id,
                    name=node.title,
                    statement=node.statement or node.title,
                )
            )
        # BOARD is the root and was attached as snapshot.board; nothing to do.


def _grade_level(title: str) -> int:
    """Best-effort numeric grade from a title like 'Class 10'. Defaults to 0
    when no number is present — never raises, never invents a board."""
    digits = "".join(ch for ch in title if ch.isdigit())
    return int(digits) if digits else 0
