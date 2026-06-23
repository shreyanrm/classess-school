"""Competitive-exam mappings are a second frame over the same graph (proposed
until confirmed, board/exam-agnostic), and school local overlays project over the
base node per scope without ever mutating it or leaking across scopes."""

from __future__ import annotations

from app._ontology import LocalOverlay, NodeKind
from app.overlays import (
    CompetitiveExamRegistry,
    LocalOverlayProjection,
)
from app.seed import SEED_ONTOLOGY_IDS, build_expanded_seed_snapshot


# -- competitive-exam mappings ---------------------------------------------


def test_exam_registry_is_exam_agnostic_and_data_driven():
    snap = build_expanded_seed_snapshot()
    reg = CompetitiveExamRegistry(snap)
    codes = reg.exam_codes()
    # Multiple exams, all neutral labels — never a baked-in exam set.
    assert "example-entrance-exam" in codes
    assert "example-scholarship-exam" in codes


def test_proposed_exam_mapping_is_not_in_the_confirmed_set():
    snap = build_expanded_seed_snapshot()
    reg = CompetitiveExamRegistry(snap)
    pending = reg.pending()
    assert pending, "the seed ships a proposed (unconfirmed) exam mapping"
    # confirmed_only excludes proposals — generate-and-verify.
    entrance = reg.for_exam("example-entrance-exam", confirmed_only=True)
    scholarship = reg.for_exam("example-scholarship-exam", confirmed_only=True)
    assert entrance and all(m.confirmed for m in entrance)
    assert scholarship == []  # its only mapping is still a proposal.


def test_exam_mappings_for_a_node_respect_the_confidence_gate():
    snap = build_expanded_seed_snapshot()
    reg = CompetitiveExamRegistry(snap)
    euclid = SEED_ONTOLOGY_IDS["outcomes"]["euclid"]
    high = reg.for_node(euclid, min_confidence=0.9)
    assert high and all(m.confidence >= 0.9 for m in high)
    # A high gate drops the low-confidence scholarship mapping entirely.
    poly = SEED_ONTOLOGY_IDS["outcomes"]["polyZeros"]
    assert reg.for_node(poly, min_confidence=0.9) == []


# -- school local overlays --------------------------------------------------


def test_overlay_aliases_and_emphasises_without_mutating_base():
    snap = build_expanded_seed_snapshot()
    base_euclid_name = snap.topic_by_id(SEED_ONTOLOGY_IDS["tEuclid"]).name
    proj = LocalOverlayProjection(snap, scope_ref="tenant-ref-0001")
    view = proj.project(SEED_ONTOLOGY_IDS["tEuclid"])
    assert view is not None
    # The school sees the alias; the base node name is unchanged.
    assert view.label == "HCF using Euclid's method"
    assert snap.topic_by_id(SEED_ONTOLOGY_IDS["tEuclid"]).name == base_euclid_name
    emph = proj.project(SEED_ONTOLOGY_IDS["tTrigIdentities"])
    assert emph is not None and emph.emphasis == "high"


def test_overlays_are_scope_isolated():
    snap = build_expanded_seed_snapshot()
    # A different scope sees the base labels — no overlay leakage.
    other = LocalOverlayProjection(snap, scope_ref="tenant-ref-9999")
    view = other.project(SEED_ONTOLOGY_IDS["tEuclid"])
    assert view is not None
    assert view.label == snap.topic_by_id(SEED_ONTOLOGY_IDS["tEuclid"]).name
    assert other.overlays_for(SEED_ONTOLOGY_IDS["tEuclid"]) == []


def test_project_unknown_node_returns_none():
    snap = build_expanded_seed_snapshot()
    proj = LocalOverlayProjection(snap, scope_ref="tenant-ref-0001")
    assert proj.project("not-a-node") is None


def test_overlay_note_and_hidden_kinds_project():
    snap = build_expanded_seed_snapshot()
    topic = SEED_ONTOLOGY_IDS["tFundThm"]
    snap.overlays.extend([
        LocalOverlay(id="ov-note", scope_ref="tenant-ref-0002", node_id=topic,
                     node_kind=NodeKind.TOPIC, overlay_kind="note",
                     value="Covered in the bridge course."),
        LocalOverlay(id="ov-hide", scope_ref="tenant-ref-0002", node_id=topic,
                     node_kind=NodeKind.TOPIC, overlay_kind="hidden", value="true"),
    ])
    proj = LocalOverlayProjection(snap, scope_ref="tenant-ref-0002")
    view = proj.project(topic)
    assert view is not None
    assert "Covered in the bridge course." in view.notes
    assert view.hidden is True
