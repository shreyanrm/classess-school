"""Balanced, explainable group-project composition.

Composes learners into teams of comparable capability by a configurable
mastery/skill mix. The composition is a RECOMMENDATION (permission ladder,
RECOMMEND rung) — a teacher accepts; it is never auto-applied. Every group and
the composition as a whole carry plain-language rationale + balance evidence.
Behavioural data carries ONLY the opaque canonical_uuid — never PII.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.groups import (
    BalanceStrategy,
    GroupConfig,
    LearnerSignal,
    compose_groups,
)


def _learners(scores: list[dict[str, float]]) -> list[LearnerSignal]:
    return [LearnerSignal(canonical_uuid=uuid4(), skills=s) for s in scores]


def _weights() -> dict[str, float]:
    return {"reasoning": 1.0, "communication": 1.0}


# ---------------------------------------------------------------------------
# Config validation.
# ---------------------------------------------------------------------------
def test_config_requires_a_dimension_to_balance_on():
    with pytest.raises(ValueError):
        GroupConfig(dimension_weights={})


def test_config_rejects_negative_weight_and_bad_size_and_tolerance():
    with pytest.raises(ValueError):
        GroupConfig(dimension_weights={"a": -1.0})
    with pytest.raises(ValueError):
        GroupConfig(dimension_weights={"a": 1.0}, target_group_size=0)
    with pytest.raises(ValueError):
        GroupConfig(dimension_weights={"a": 1.0}, balance_tolerance=1.5)


def test_weighted_capability_clamps_and_treats_unknown_as_zero():
    lr = LearnerSignal(canonical_uuid=uuid4(), skills={"reasoning": 0.8})  # communication absent
    cap = lr.weighted_capability({"reasoning": 1.0, "communication": 1.0})
    # (0.8 + 0.0) / 2 = 0.4 — an unknown dimension is not assumed strong.
    assert cap == 0.4
    # Out-of-range scores are clamped to [0,1].
    hi = LearnerSignal(canonical_uuid=uuid4(), skills={"reasoning": 5.0})
    assert hi.weighted_capability({"reasoning": 1.0}) == 1.0


# ---------------------------------------------------------------------------
# MIX — balanced, comparable teams.
# ---------------------------------------------------------------------------
def test_mix_produces_balanced_comparable_teams():
    # A clear capability gradient; MIX should spread it so team means are close.
    scores = [
        {"reasoning": v, "communication": v}
        for v in (0.95, 0.9, 0.8, 0.7, 0.55, 0.45, 0.3, 0.1)
    ]
    learners = _learners(scores)
    config = GroupConfig(dimension_weights=_weights(), target_group_size=4, strategy=BalanceStrategy.MIX)
    comp = compose_groups(learners, config)

    assert comp.strategy is BalanceStrategy.MIX
    assert comp.group_count == 2
    # Every learner placed; no PII leaked — members are uuids only.
    placed = [m for g in comp.groups for m in g.members]
    assert len(placed) == len(learners)
    assert set(placed) == {lr.canonical_uuid for lr in learners}
    # Teams are comparable: spread within tolerance and flagged balanced.
    assert comp.spread <= config.balance_tolerance
    assert comp.balanced is True


def test_mix_is_more_balanced_than_a_clustered_split():
    scores = [
        {"reasoning": v, "communication": v}
        for v in (0.95, 0.9, 0.8, 0.7, 0.55, 0.45, 0.3, 0.1)
    ]
    learners = _learners(scores)
    mix = compose_groups(learners, GroupConfig(dimension_weights=_weights(), target_group_size=4, strategy=BalanceStrategy.MIX))
    cluster = compose_groups(learners, GroupConfig(dimension_weights=_weights(), target_group_size=4, strategy=BalanceStrategy.CLUSTER))
    # The whole point of MIX: smaller spread of team means than CLUSTER.
    assert mix.spread < cluster.spread


# ---------------------------------------------------------------------------
# Explainability + evidence.
# ---------------------------------------------------------------------------
def test_composition_is_explainable_with_evidence_per_group():
    learners = _learners([{"reasoning": 0.8, "communication": 0.6}] * 6)
    config = GroupConfig(dimension_weights=_weights(), target_group_size=3)
    comp = compose_groups(learners, config)

    assert comp.rationale  # plain-language top-level explanation
    for g in comp.groups:
        assert g.rationale
        # Per-dimension averages are the evidence behind the placement.
        assert set(g.dimension_means.keys()) == set(_weights().keys())
        assert 0.0 <= g.capability_mean <= 1.0
        for v in g.dimension_means.values():
            assert 0.0 <= v <= 1.0


def test_balance_metric_and_tolerance_are_reported():
    learners = _learners([{"reasoning": v, "communication": v} for v in (0.9, 0.8, 0.2, 0.1)])
    config = GroupConfig(dimension_weights=_weights(), target_group_size=2, balance_tolerance=0.15)
    comp = compose_groups(learners, config)
    assert comp.balance_tolerance == 0.15
    assert isinstance(comp.spread, float)
    # The balanced flag is consistent with the reported spread vs tolerance (MIX).
    assert comp.balanced == (comp.spread <= comp.balance_tolerance)


def test_configurable_dimension_weights_change_capability_ranking():
    # Learner X strong at reasoning; learner Y strong at communication.
    x = LearnerSignal(canonical_uuid=uuid4(), skills={"reasoning": 1.0, "communication": 0.0})
    y = LearnerSignal(canonical_uuid=uuid4(), skills={"reasoning": 0.0, "communication": 1.0})
    # Weight reasoning heavily -> X ranks above Y.
    cap_x = x.weighted_capability({"reasoning": 3.0, "communication": 1.0})
    cap_y = y.weighted_capability({"reasoning": 3.0, "communication": 1.0})
    assert cap_x > cap_y


# ---------------------------------------------------------------------------
# Permission ladder + PII.
# ---------------------------------------------------------------------------
def test_composition_is_a_recommendation_never_auto_applied():
    learners = _learners([{"reasoning": 0.5, "communication": 0.5}] * 4)
    comp = compose_groups(learners, GroupConfig(dimension_weights=_weights()))
    assert comp.rung == "recommend"


def test_no_pii_only_opaque_uuids_in_groups():
    learners = _learners([{"reasoning": 0.5, "communication": 0.5}] * 5)
    comp = compose_groups(learners, GroupConfig(dimension_weights=_weights(), target_group_size=2))
    for g in comp.groups:
        for member in g.members:
            assert type(member).__name__ == "UUID"


# ---------------------------------------------------------------------------
# CLUSTER — intentional near-peer tiering.
# ---------------------------------------------------------------------------
def test_cluster_groups_like_with_like():
    scores = [{"reasoning": v, "communication": v} for v in (0.9, 0.85, 0.2, 0.15)]
    learners = _learners(scores)
    comp = compose_groups(learners, GroupConfig(dimension_weights=_weights(), target_group_size=2, strategy=BalanceStrategy.CLUSTER))
    assert comp.strategy is BalanceStrategy.CLUSTER
    # Cluster intentionally tiers: it is reported balanced (spread is intended),
    # and the strongest team mean clearly exceeds the weakest.
    assert comp.balanced is True
    means = sorted(g.capability_mean for g in comp.groups)
    assert means[-1] > means[0]


# ---------------------------------------------------------------------------
# Edge / degenerate inputs.
# ---------------------------------------------------------------------------
def test_no_learners_yields_empty_balanced_composition():
    comp = compose_groups([], GroupConfig(dimension_weights=_weights()))
    assert comp.groups == []
    assert comp.balanced is True
    assert comp.group_count == 0
    assert comp.rationale


def test_every_learner_is_placed_exactly_once():
    learners = _learners([{"reasoning": 0.5, "communication": 0.5}] * 7)
    comp = compose_groups(learners, GroupConfig(dimension_weights=_weights(), target_group_size=3))
    placed = [m for g in comp.groups for m in g.members]
    assert len(placed) == 7
    assert len(set(placed)) == 7  # no duplicates
    assert comp.unplaced == []
