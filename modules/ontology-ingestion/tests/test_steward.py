"""The prerequisite-edge steward: proposed edges start UNCONFIRMED and are never
trusted until a human steward confirms them (the central A2 law)."""

from __future__ import annotations

import pytest

from app._ontology import PrerequisiteKind
from app.embeddings import SemanticIndex
from app.seed import SEED_ONTOLOGY_IDS, build_seed_snapshot
from app.steward import PrerequisiteSteward

STEWARD_REF = "5ee0a000-0000-4000-8000-000000000001"


def test_proposed_edges_start_unconfirmed():
    snap = build_seed_snapshot()
    # Strip pre-confirmed seed edges so the steward proposes fresh ones.
    snap.edges = []
    steward = PrerequisiteSteward(snap)
    proposals = steward.propose_from_snapshot()
    assert proposals, "steward should propose sequence-adjacency edges"
    # EVERY proposal is unconfirmed and carries an explainable rationale.
    for p in proposals:
        assert p.confirmed is False
        assert p.edge.confirmed is False
        assert p.edge.rationale
    # None are trusted for routing yet.
    assert steward.trusted_edges() == []
    assert len(steward.pending()) == len(proposals)


def test_confirmation_requires_a_human_steward_ref():
    snap = build_seed_snapshot()
    snap.edges = []
    steward = PrerequisiteSteward(snap)
    proposal = steward.propose_from_snapshot()[0]

    # Confirming with no steward ref is refused (permission ladder).
    with pytest.raises(PermissionError):
        steward.confirm(proposal.id, steward_ref="")

    # With a human ref it becomes trusted.
    confirmed = steward.confirm(proposal.id, steward_ref=STEWARD_REF)
    assert confirmed.confirmed is True
    assert confirmed in steward.trusted_edges()
    # The decision is recorded with the opaque steward ref.
    decisions = steward.decisions()
    assert decisions[-1].steward_ref == STEWARD_REF
    assert decisions[-1].decision == "confirmed"


def test_only_confirmed_edges_are_trusted():
    snap = build_seed_snapshot()
    steward = PrerequisiteSteward(snap)
    # The seed ships 8 confirmed + 1 proposed edge.
    trusted = steward.trusted_edges()
    pending = steward.pending()
    assert len(trusted) == 8
    assert len(pending) == 1
    # The one pending edge is the irrational -> trig-ratios proposal.
    assert pending[0].edge.from_topic_id == SEED_ONTOLOGY_IDS["tIrrational"]
    assert pending[0].edge.to_topic_id == SEED_ONTOLOGY_IDS["tTrigRatios"]
    assert pending[0].edge.confirmed is False


def test_reject_removes_a_proposal_and_requires_a_ref():
    snap = build_seed_snapshot()
    snap.edges = []
    steward = PrerequisiteSteward(snap)
    proposal = steward.propose_from_snapshot()[0]

    with pytest.raises(PermissionError):
        steward.reject(proposal.id, steward_ref="")

    steward.reject(proposal.id, steward_ref=STEWARD_REF)
    assert proposal.id not in {p.id for p in steward.proposals()}
    assert steward.decisions()[-1].decision == "rejected"


def test_self_edge_and_unknown_topic_are_refused():
    snap = build_seed_snapshot()
    steward = PrerequisiteSteward(snap)
    t = SEED_ONTOLOGY_IDS["tEuclid"]
    with pytest.raises(ValueError):
        steward.propose(from_topic_id=t, to_topic_id=t, kind=PrerequisiteKind.HARD,
                        rationale="x", confidence=0.9)
    with pytest.raises(ValueError):
        steward.propose(from_topic_id=t, to_topic_id="not-a-topic",
                        kind=PrerequisiteKind.HARD, rationale="x", confidence=0.9)


def test_semantic_proposals_are_also_unconfirmed_candidates():
    snap = build_seed_snapshot()
    snap.edges = []
    # Index topic text so the steward can raise similarity proposals.
    index = SemanticIndex.create()
    index.index_many((t.id, t.name) for t in snap.topics)
    steward = PrerequisiteSteward(snap)
    proposals = steward.propose_from_snapshot(semantic_index=index)
    # Whatever the heuristics raise, none is auto-trusted.
    assert all(p.confirmed is False for p in proposals)
    assert steward.trusted_edges() == []


def test_proposed_edge_payloads_carry_no_pii():
    snap = build_seed_snapshot()
    snap.edges = []
    steward = PrerequisiteSteward(snap)
    for p in steward.propose_from_snapshot():
        # An edge holds only opaque topic ids, a kind, a rationale, a flag.
        keys = set(vars(p.edge).keys())
        forbidden = {"name", "email", "phone", "student", "teacher_name"}
        assert not (forbidden & keys)
