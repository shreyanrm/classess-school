"""The richer OFFLINE seed expansion grows the same neutral board substantially,
stays referentially consistent, keeps the canonical seed intact, and ships its
cross-grade prerequisite edge UNCONFIRMED. No board lock-in, no network."""

from __future__ import annotations

from app._ontology import PrerequisiteKind
from app.seed import (
    EXPANDED_SEED_IDS,
    build_expanded_seed_snapshot,
    build_seed_snapshot,
)


def test_expansion_is_substantially_larger_same_board():
    base = build_seed_snapshot()
    snap = build_expanded_seed_snapshot()
    # Same NEUTRAL board — a label, never a real-board lock-in.
    assert snap.board.code == base.board.code == "example-state-board"
    # Substantially larger than the base seed across every level.
    assert len(snap.grades) > len(base.grades)
    assert len(snap.subjects) > len(base.subjects)
    assert len(snap.topics) > len(base.topics)
    assert len(snap.outcomes) > len(base.outcomes)
    assert len(snap.competencies) > len(base.competencies)
    assert len(snap.edges) > len(base.edges)


def test_expansion_preserves_the_canonical_seed():
    base = build_seed_snapshot()
    snap = build_expanded_seed_snapshot()
    base_topic_ids = base.topic_ids()
    snap_topic_ids = snap.topic_ids()
    # Every canonical-seed topic survives unchanged in the expansion.
    assert base_topic_ids.issubset(snap_topic_ids)
    base_edge_ids = {e.id for e in base.edges}
    assert base_edge_ids.issubset({e.id for e in snap.edges})


def test_expansion_referential_integrity():
    snap = build_expanded_seed_snapshot()
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


def test_expansion_ids_are_unique():
    snap = build_expanded_seed_snapshot()
    all_ids = (
        [g.id for g in snap.grades]
        + [s.id for s in snap.subjects]
        + [u.id for u in snap.units]
        + [c.id for c in snap.chapters]
        + [t.id for t in snap.topics]
        + [o.id for o in snap.outcomes]
        + [c.id for c in snap.competencies]
        + [e.id for e in snap.edges]
    )
    assert len(all_ids) == len(set(all_ids))  # no id collisions.


def test_expansion_proposed_cross_grade_edge_is_unconfirmed():
    snap = build_expanded_seed_snapshot()
    proposed = [
        e for e in snap.edges
        if not e.confirmed and e.from_topic_id == EXPANDED_SEED_IDS["tFactorThm9"]
    ]
    assert len(proposed) == 1
    assert proposed[0].kind is PrerequisiteKind.SOFT
    assert proposed[0].confirmed is False


def test_expansion_adds_a_second_grade_and_third_subject():
    snap = build_expanded_seed_snapshot()
    levels = {g.level for g in snap.grades}
    assert {9, 10}.issubset(levels)
    subject_names = {s.name for s in snap.subjects}
    assert "Chemistry" in subject_names
