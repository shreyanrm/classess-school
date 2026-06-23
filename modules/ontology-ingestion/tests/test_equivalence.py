"""Cross-board equivalence: symmetric, board-agnostic, confidence-gated, and
proposal-then-confirm (a proposal is never auto-trusted)."""

from __future__ import annotations

import pytest

from app._ontology import NodeKind
from app.equivalence import BoardNodeRef, EquivalenceRegistry

ALPHA = BoardNodeRef("board-alpha", "node-a", NodeKind.TOPIC, label="HCF by division")
BETA = BoardNodeRef("board-beta", "node-b", NodeKind.TOPIC, label="Euclidean algorithm")
GAMMA = BoardNodeRef("board-gamma", "node-c", NodeKind.TOPIC, label="GCD method")


def test_cross_board_equivalence_is_symmetric():
    reg = EquivalenceRegistry()
    reg.add(ALPHA, BETA, confidence=0.9, method="steward", confirmed=True)

    # Lookup from EITHER side finds the other.
    from_alpha = reg.equivalents_of(ALPHA)
    from_beta = reg.equivalents_of(BETA)
    assert [e.right.key() for e in from_alpha] == [BETA.key()]
    assert [e.right.key() for e in from_beta] == [ALPHA.key()]

    # Symmetric confidence — same both directions.
    assert from_alpha[0].confidence == from_beta[0].confidence == 0.9

    # are_equivalent is order-independent.
    assert reg.are_equivalent(ALPHA, BETA) is True
    assert reg.are_equivalent(BETA, ALPHA) is True


def test_no_board_is_hard_coded():
    reg = EquivalenceRegistry()
    reg.add(ALPHA, BETA, confidence=0.8)
    reg.add(BETA, GAMMA, confidence=0.7)
    # The registry is purely data-driven over board CODE labels; it never
    # special-cases a board. Any set of codes is fine.
    assert reg.board_codes() == {"board-alpha", "board-beta", "board-gamma"}


def test_pair_is_deduplicated_regardless_of_order():
    reg = EquivalenceRegistry()
    reg.add(ALPHA, BETA, confidence=0.6)
    reg.add(BETA, ALPHA, confidence=0.9)  # same pair, reversed order.
    # One canonical pair, updated (not duplicated).
    assert len(reg) == 1
    assert reg.equivalents_of(ALPHA)[0].confidence == 0.9


def test_confidence_gate_filters_low_confidence_mappings():
    reg = EquivalenceRegistry()
    reg.add(ALPHA, BETA, confidence=0.4)
    reg.add(ALPHA, GAMMA, confidence=0.95)
    high = reg.equivalents_of(ALPHA, min_confidence=0.5)
    assert [e.right.key() for e in high] == [GAMMA.key()]


def test_proposed_equivalence_is_not_auto_trusted():
    reg = EquivalenceRegistry()
    reg.propose(ALPHA, BETA, confidence=0.7, method="semantic-index")
    # Present but unconfirmed; confirmed_only excludes it.
    assert reg.are_equivalent(ALPHA, BETA) is True
    assert reg.are_equivalent(ALPHA, BETA, confirmed_only=True) is False
    assert reg.equivalents_of(ALPHA, confirmed_only=True) == []

    # A steward confirms it (symmetric — confirming applies both directions).
    reg.confirm(ALPHA, BETA)
    assert reg.are_equivalent(ALPHA, BETA, confirmed_only=True) is True
    assert reg.equivalents_of(BETA, confirmed_only=True)[0].right.key() == ALPHA.key()


def test_self_mapping_is_refused():
    reg = EquivalenceRegistry()
    with pytest.raises(ValueError):
        reg.add(ALPHA, ALPHA, confidence=1.0)


def test_confirming_unknown_pair_raises():
    reg = EquivalenceRegistry()
    with pytest.raises(KeyError):
        reg.confirm(ALPHA, BETA)


def test_confidence_is_clamped_to_unit_interval():
    reg = EquivalenceRegistry()
    e = reg.add(ALPHA, BETA, confidence=1.7)
    assert e.confidence == 1.0
    e2 = reg.add(ALPHA, GAMMA, confidence=-0.5)
    assert e2.confidence == 0.0
