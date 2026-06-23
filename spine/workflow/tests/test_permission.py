"""Permission-ladder enforcement tests (INVARIANT 8).

The keystone guarantees: a consequential action is pinned to
execute_with_permission, never safe_automatic, and can never auto-fire; low-risk
in-policy actions may be safe_automatic; anything unknown fails closed to
recommend.
"""

from __future__ import annotations

import pytest

from app.models import LadderStage
from app.permission import (
    CONSEQUENTIAL_VERBS,
    ActionDescriptor,
    LadderPolicy,
    classify_action,
    is_consequential,
    may_autofire,
)


@pytest.mark.parametrize("verb", sorted(CONSEQUENTIAL_VERBS))
def test_consequential_verb_pins_to_execute_with_permission_and_never_autofires(verb):
    action = ActionDescriptor(kind=f"do_{verb}", effect_verb=verb)
    decision = classify_action(action)

    assert decision.is_consequential is True
    assert decision.stage == LadderStage.EXECUTE_WITH_PERMISSION
    assert decision.may_autofire is False
    assert decision.requires_human_approval is True
    assert may_autofire(action) is False


def test_consequential_verb_is_case_and_whitespace_insensitive():
    assert is_consequential(ActionDescriptor(kind="x", effect_verb="  SEND ")) is True


def test_safe_automatic_for_allow_listed_non_consequential():
    action = ActionDescriptor(kind="recompute_mastery", effect_verb="recompute")
    decision = classify_action(action)

    assert decision.is_consequential is False
    assert decision.stage == LadderStage.SAFE_AUTOMATIC
    assert decision.may_autofire is True
    assert decision.requires_human_approval is False


def test_unknown_non_consequential_fails_closed_to_recommend():
    action = ActionDescriptor(kind="some_new_action", effect_verb="compute")
    decision = classify_action(action)

    assert decision.is_consequential is False
    assert decision.stage == LadderStage.RECOMMEND
    assert decision.may_autofire is False
    assert decision.policy_basis == "fail-closed-default"


def test_external_facing_non_consequential_stays_manual_under_default_policy():
    # Even if allow-listed, an external-facing effect is kept manual.
    policy = LadderPolicy(
        safe_automatic_kinds=frozenset({"refresh_dashboard"}),
        external_effects_always_manual=True,
    )
    action = ActionDescriptor(
        kind="refresh_dashboard", effect_verb="refresh", targets_external=True
    )
    decision = classify_action(action, policy)
    assert decision.stage == LadderStage.RECOMMEND
    assert decision.may_autofire is False


def test_grade_is_consequential():
    # Grading a learner is a high-stakes judgment and must never auto-fire.
    assert is_consequential(ActionDescriptor(kind="grade_paper", effect_verb="grade"))
    assert classify_action(
        ActionDescriptor(kind="grade_paper", effect_verb="grade")
    ).may_autofire is False
