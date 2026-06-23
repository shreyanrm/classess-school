"""Ingestion maps source curriculum into the ontology types, board-agnostically,
degrades gracefully, and never trusts a node silently (confidence gate)."""

from __future__ import annotations

from app._ontology import NodeKind
from app.config import OntologySettings
from app.ingest import (
    CurriculumIngester,
    NullDocumentUnderstanding,
    OutlineNode,
    SourceDocument,
    default_document_understanding,
)


def _structured_document(board_code: str, board_name: str) -> SourceDocument:
    """A fully structured publisher/standards outline for one grade + subject."""
    outline = (
        OutlineNode(
            kind=NodeKind.GRADE,
            title="Class 9",
            children=(
                OutlineNode(
                    kind=NodeKind.SUBJECT,
                    title="Mathematics",
                    children=(
                        OutlineNode(
                            kind=NodeKind.UNIT,
                            title="Number Systems",
                            sequence=0,
                            children=(
                                OutlineNode(
                                    kind=NodeKind.CHAPTER,
                                    title="Real Numbers",
                                    sequence=0,
                                    children=(
                                        OutlineNode(
                                            kind=NodeKind.TOPIC,
                                            title="Rational and Irrational Numbers",
                                            sequence=0,
                                            children=(
                                                OutlineNode(
                                                    kind=NodeKind.OUTCOME,
                                                    title="classify-numbers",
                                                    statement="Classifies a number as rational or irrational and locates it on the number line.",
                                                ),
                                            ),
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )
    return SourceDocument(
        source_ref="doc-ref-001",
        board_code=board_code,
        board_name=board_name,
        region="Example Region",
        raw_outline=outline,
    )


def test_ingestion_maps_into_ontology_types():
    ingester = CurriculumIngester(settings=OntologySettings())  # degraded.
    result = ingester.ingest(_structured_document("example-state-board", "Example State Board"))
    snap = result.snapshot

    # The board is a labelled node carried from the source.
    assert snap.board.code == "example-state-board"
    assert snap.board.kind is NodeKind.BOARD

    # Every level was mapped onto its typed table, under the right parent.
    assert len(snap.grades) == 1 and snap.grades[0].level == 9
    assert len(snap.subjects) == 1 and snap.subjects[0].grade_id == snap.grades[0].id
    assert len(snap.units) == 1 and snap.units[0].subject_id == snap.subjects[0].id
    assert len(snap.chapters) == 1 and snap.chapters[0].unit_id == snap.units[0].id
    assert len(snap.topics) == 1 and snap.topics[0].chapter_id == snap.chapters[0].id
    assert len(snap.outcomes) == 1 and snap.outcomes[0].topic_id == snap.topics[0].id
    # The outcome carries its can-do statement, not just a title.
    assert "rational" in snap.outcomes[0].statement.lower()


def test_ingested_nodes_are_always_drafts():
    ingester = CurriculumIngester(settings=OntologySettings())
    result = ingester.ingest(_structured_document("example-state-board", "Example State Board"))
    # Ingestion never publishes trusted nodes — promotion is a separate human act.
    assert result.draft is True


def test_no_provider_records_pending_extraction_never_invents():
    # Unstructured document + no provider -> pending extraction, no invention.
    ingester = CurriculumIngester(settings=OntologySettings())
    doc = SourceDocument(
        source_ref="scan-002",
        board_code="some-board",
        board_name="Some Board",
        raw_outline=(),  # nothing structured; no provider available.
    )
    result = ingester.ingest(doc)
    assert result.pending_extraction is True
    assert result.nodes == []          # no fabricated structure.
    assert result.available is False
    # The board node still exists (it was labelled in the source).
    assert result.snapshot.board.code == "some-board"


def test_null_provider_reports_unavailable_and_names_env():
    provider = NullDocumentUnderstanding()
    doc = SourceDocument(source_ref="x", board_code="b", board_name="B")
    res = provider.understand(doc)
    assert res.available is False
    assert res.provider == "none"
    # Degraded detail names the env var (by NAME) the live path would read.
    assert "doc_understanding_key" in (res.detail or "")


def test_confidence_gate_flags_low_confidence_nodes_for_review():
    outline = (
        OutlineNode(
            kind=NodeKind.GRADE,
            title="Class 10",
            confidence=0.95,
            children=(
                OutlineNode(
                    kind=NodeKind.SUBJECT,
                    title="Science",
                    confidence=0.30,  # below the gate.
                ),
            ),
        ),
    )
    doc = SourceDocument(
        source_ref="d", board_code="b", board_name="B", raw_outline=outline
    )
    ingester = CurriculumIngester(settings=OntologySettings(), confidence_gate=0.6)
    result = ingester.ingest(doc)
    flagged = {n.title for n in result.needs_review}
    assert "Science" in flagged       # low-confidence flagged.
    assert "Class 10" not in flagged  # high-confidence not flagged.


def test_no_board_is_hard_coded_same_pipeline_any_board():
    # The SAME ingester, run on two different boards, maps each faithfully —
    # nothing about a board is baked into the code path.
    ingester = CurriculumIngester(settings=OntologySettings())
    a = ingester.ingest(_structured_document("board-alpha", "Board Alpha"))
    b = ingester.ingest(_structured_document("board-beta", "Board Beta"))
    assert a.snapshot.board.code == "board-alpha"
    assert b.snapshot.board.code == "board-beta"
    # Distinct boards yield distinct (deterministic) node ids — no collision,
    # no shared board assumption.
    assert a.snapshot.topics[0].id != b.snapshot.topics[0].id
    # Same board re-ingested is idempotent (deterministic ids).
    a2 = ingester.ingest(_structured_document("board-alpha", "Board Alpha"))
    assert a.snapshot.topics[0].id == a2.snapshot.topics[0].id


def test_default_provider_is_null_when_degraded():
    provider = default_document_understanding(OntologySettings())
    assert isinstance(provider, NullDocumentUnderstanding)
