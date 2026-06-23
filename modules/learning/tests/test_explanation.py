"""Multiple selectable explanation styles for the reveal (d12)."""

from __future__ import annotations

import pytest

from learning import explanation
from learning.explanation import (
    ALL_EXPLANATION_STYLES,
    ExplanationStyle,
    assert_socratic_poses,
    choose_style,
)


def test_six_styles_each_have_a_contract():
    for s in ALL_EXPLANATION_STYLES:
        assert s in explanation.STYLE_CONTRACTS
    assert len(ALL_EXPLANATION_STYLES) == len(set(ALL_EXPLANATION_STYLES))


def test_learner_preference_wins():
    c = choose_style(learner_preference=ExplanationStyle.ANALOGY)
    assert c.style is ExplanationStyle.ANALOGY
    assert c.from_preference is True


def test_conceptual_gap_overrides_worked_example_preference():
    # A conceptual gap will not shift with another worked example, so the
    # preference is overridden toward the underlying idea.
    c = choose_style(gap_type="conceptual", learner_preference=ExplanationStyle.WORKED_EXAMPLE)
    assert c.style is ExplanationStyle.INTUITION
    assert c.from_preference is False


def test_procedural_gap_selects_step_by_step():
    c = choose_style(gap_type="procedural")
    assert c.style is ExplanationStyle.STEP_BY_STEP


def test_speed_gap_selects_worked_example():
    c = choose_style(gap_type="speed")
    assert c.style is ExplanationStyle.WORKED_EXAMPLE


def test_default_varies_from_last_style():
    c = choose_style(last_style_used=ExplanationStyle.WORKED_EXAMPLE)
    assert c.style is not ExplanationStyle.WORKED_EXAMPLE


def test_every_choice_is_explainable():
    c = choose_style(gap_type="application")
    assert c.reason and isinstance(c.reason, str)


def test_socratic_must_pose_a_question():
    with pytest.raises(ValueError):
        assert_socratic_poses("This is how it works.", style=ExplanationStyle.SOCRATIC)
    # A real Socratic line poses, so it passes.
    assert_socratic_poses("What do you notice about the two numbers?", style=ExplanationStyle.SOCRATIC)


def test_non_socratic_style_not_required_to_pose():
    assert_socratic_poses("Here is a worked example.", style=ExplanationStyle.WORKED_EXAMPLE)


def test_labels_have_no_emoji_or_exclaim():
    for c in explanation.STYLE_CONTRACTS.values():
        assert "!" not in c.learner_label
