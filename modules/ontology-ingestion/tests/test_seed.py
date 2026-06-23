"""The Python seed view mirrors the contract snapshot, is internally consistent,
and ships its one prerequisite edge UNCONFIRMED."""

from __future__ import annotations

from app._ontology import NodeKind, PrerequisiteKind
from app.seed import SEED_ONTOLOGY_IDS, build_seed_snapshot


def test_seed_shape_matches_contract_counts():
    snap = build_seed_snapshot()
    assert snap.board.code == "example-state-board"   # NOT a real board.
    assert len(snap.grades) == 1
    assert len(snap.subjects) == 2
    assert len(snap.units) == 5
    assert len(snap.chapters) == 6
    assert len(snap.topics) == 13
    assert len(snap.outcomes) == 13
    assert len(snap.competencies) == 4
    assert len(snap.edges) == 9
    assert len(snap.equivalences) == 2


def test_seed_referential_integrity():
    snap = build_seed_snapshot()
    grade_ids = {g.id for g in snap.grades}
    subject_ids = {s.id for s in snap.subjects}
    unit_ids = {u.id for u in snap.units}
    chapter_ids = {c.id for c in snap.chapters}
    topic_ids = snap.topic_ids()
    outcome_ids = {o.id for o in snap.outcomes}

    assert all(s.grade_id in grade_ids for s in snap.subjects)
    assert all(u.subject_id in subject_ids for u in snap.units)
    assert all(c.unit_id in unit_ids for c in snap.chapters)
    assert all(t.chapter_id in chapter_ids for t in snap.topics)
    assert all(o.topic_id in topic_ids for o in snap.outcomes)
    for edge in snap.edges:
        assert edge.from_topic_id in topic_ids
        assert edge.to_topic_id in topic_ids
    for comp in snap.competencies:
        assert comp.subject_id in subject_ids
        assert all(oid in outcome_ids for oid in comp.outcome_ids)


def test_seed_proposed_edge_is_unconfirmed():
    snap = build_seed_snapshot()
    proposed = [e for e in snap.edges if not e.confirmed]
    assert len(proposed) == 1
    edge = proposed[0]
    assert edge.from_topic_id == SEED_ONTOLOGY_IDS["tIrrational"]
    assert edge.to_topic_id == SEED_ONTOLOGY_IDS["tTrigRatios"]
    assert edge.kind is PrerequisiteKind.SOFT


def test_equivalences_point_at_another_labelled_board():
    snap = build_seed_snapshot()
    for eq in snap.equivalences:
        assert eq.node_kind is NodeKind.TOPIC
        # The other board is a CODE label, not this board — board-agnostic.
        assert eq.equivalent_board_code != snap.board.code
        assert 0.0 <= eq.confidence <= 1.0
