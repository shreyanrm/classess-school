"""The ontology deepens below competency to the doc's full chain
(… competency → skill → question → resource) and carries competitive-exam
mappings, school local overlays, and curriculum version stamps — all on the same
neutral board, offline, PII-free, and additive over the canonical seed."""

from __future__ import annotations

from app._ontology import (
    CONTAINER_ORDER,
    NodeKind,
    OntologySnapshot,
)
from app.seed import (
    EXPANDED_SEED_IDS,
    build_expanded_seed_snapshot,
    build_seed_snapshot,
)


def test_full_chain_node_kinds_exist():
    # The doc's chain ends at skill → question → resource.
    for name in ("SKILL", "QUESTION", "RESOURCE"):
        assert hasattr(NodeKind, name)
    # Containers stop at outcome; the leaves are not in the container chain.
    assert NodeKind.OUTCOME in CONTAINER_ORDER
    assert NodeKind.SKILL not in CONTAINER_ORDER


def test_expansion_adds_deep_nodes_below_competency():
    snap = build_expanded_seed_snapshot()
    assert snap.skills, "expansion should add skills below competency"
    assert snap.questions, "expansion should add questions below skill"
    assert snap.resources, "expansion should add resources"
    # Each kind tags itself correctly.
    assert all(s.kind is NodeKind.SKILL for s in snap.skills)
    assert all(q.kind is NodeKind.QUESTION for q in snap.questions)
    assert all(r.kind is NodeKind.RESOURCE for r in snap.resources)


def test_deep_nodes_are_referentially_consistent():
    snap = build_expanded_seed_snapshot()
    competency_ids = {c.id for c in snap.competencies}
    skill_ids = {s.id for s in snap.skills}
    outcome_ids = snap.outcome_ids()
    node_ids = snap.node_ids()
    # Skills hang off real competencies and list real outcomes.
    for skill in snap.skills:
        assert skill.competency_id in competency_ids
        assert all(oid in outcome_ids for oid in skill.outcome_ids)
    # Questions assess real skills and (when set) real outcomes.
    for q in snap.questions:
        assert q.skill_id in skill_ids
        if q.outcome_id is not None:
            assert q.outcome_id in outcome_ids
    # Resources attach to real nodes.
    for r in snap.resources:
        assert r.target_id in node_ids


def test_resource_holds_an_opaque_handle_not_content():
    snap = build_expanded_seed_snapshot()
    for r in snap.resources:
        # An opaque content-store handle, never raw bytes/content/PII.
        assert "://" in r.resource_ref
        keys = set(vars(r).keys())
        assert not ({"student", "email", "name_of"} & keys)


def test_canonical_seed_is_untouched_by_deepening():
    # The count-locked canonical seed gains no deep nodes — additive only.
    base = build_seed_snapshot()
    assert base.skills == []
    assert base.questions == []
    assert base.resources == []
    assert base.exam_mappings == []
    assert base.overlays == []
    assert base.versions == []


def test_expansion_node_ids_remain_unique_including_deep():
    snap = build_expanded_seed_snapshot()
    all_ids = (
        [g.id for g in snap.grades]
        + [s.id for s in snap.subjects]
        + [u.id for u in snap.units]
        + [c.id for c in snap.chapters]
        + [t.id for t in snap.topics]
        + [o.id for o in snap.outcomes]
        + [c.id for c in snap.competencies]
        + [s.id for s in snap.skills]
        + [q.id for q in snap.questions]
        + [r.id for r in snap.resources]
        + [e.id for e in snap.edges]
        + [m.id for m in snap.exam_mappings]
        + [ov.id for ov in snap.overlays]
        + [v.id for v in snap.versions]
    )
    assert len(all_ids) == len(set(all_ids))


def test_empty_snapshot_has_all_deep_tables():
    from app.seed import build_seed_snapshot

    snap = build_seed_snapshot()
    # The new tables exist on every snapshot (default empty lists).
    assert isinstance(snap, OntologySnapshot)
    for attr in ("skills", "questions", "resources", "exam_mappings", "overlays", "versions"):
        assert isinstance(getattr(snap, attr), list)
