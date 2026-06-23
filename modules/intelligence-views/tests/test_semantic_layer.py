"""One metric, defined once, computed the same everywhere — the keystone of B11.

These tests enforce that a metric is defined exactly once and that every view
gets the SAME number from the SAME definition.
"""

from __future__ import annotations

import pytest

from app.semantic_layer import (
    MetricContext,
    MetricDefinition,
    MetricGrain,
    MetricRedefinitionError,
    SemanticLayer,
    build_default_semantic_layer,
)
from .conftest import T_TRIG_RATIOS, has_no_emoji


def test_redefining_a_metric_is_refused():
    layer = SemanticLayer()
    layer.define(
        key="topic_mastery",
        label="Mastery",
        definition="def",
        grain=MetricGrain.TOPIC,
        unit="ratio",
        compute=lambda ctx: 0.5,
    )
    with pytest.raises(MetricRedefinitionError):
        layer.define(
            key="topic_mastery",
            label="Mastery (forked)",
            definition="a different definition",
            grain=MetricGrain.TOPIC,
            unit="ratio",
            compute=lambda ctx: 0.9,  # a DIFFERENT computation under the same key
        )


def test_reregistering_the_identical_definition_is_idempotent():
    layer = SemanticLayer()
    d = MetricDefinition(
        key="x", label="X", definition="d", grain=MetricGrain.TOPIC,
        unit="ratio", compute=lambda ctx: 0.3,
    )
    layer.register(d)
    layer.register(d)  # same object — harmless
    assert layer.keys() == ["x"]


def test_unknown_metric_is_refused_not_approximated():
    layer = build_default_semantic_layer()
    with pytest.raises(KeyError):
        layer.get("not_a_metric")


def test_same_metric_same_number_for_two_callers(strong_cohort):
    """Two independent computations of the same metric over the same data agree —
    the property that lets dashboards, quadrant, and ask-anything match."""
    profiles, topic_id = strong_cohort
    layer = build_default_semantic_layer()
    ctx = MetricContext(profiles=profiles, topic_id=topic_id, extra={})
    a = layer.compute("topic_mastery", ctx)
    b = layer.compute("topic_mastery", ctx)
    assert a.value == b.value
    # A fresh layer with the same definitions yields the same number too.
    other = build_default_semantic_layer()
    assert other.compute("topic_mastery", ctx).value == a.value


def test_ratio_metrics_are_clamped_to_unit_interval(strong_cohort):
    profiles, topic_id = strong_cohort
    layer = build_default_semantic_layer()
    ctx = MetricContext(profiles=profiles, topic_id=topic_id, extra={})
    for key in ("topic_mastery", "independence", "confirmed_gap_share", "coverage", "effort"):
        mv = layer.compute(key, ctx)
        assert 0.0 <= mv.value <= 1.0


def test_non_learner_safe_metric_carries_plain_language(strong_cohort):
    """A non-learner-safe metric (mastery) must always have a plain-language band —
    a learner/parent never sees the raw number/formula."""
    profiles, topic_id = strong_cohort
    layer = build_default_semantic_layer()
    ctx = MetricContext(profiles=profiles, topic_id=topic_id, extra={})
    mv = layer.compute("topic_mastery", ctx)
    assert mv.learner_safe is False
    assert mv.plain_language
    assert mv.shown_to_learner() == mv.plain_language


def test_coverage_metric_uses_supplied_map():
    layer = build_default_semantic_layer()
    ctx = MetricContext(profiles=[], topic_id=T_TRIG_RATIOS, extra={"coverage": {T_TRIG_RATIOS: (3, 4)}})
    assert layer.compute("coverage", ctx).value == pytest.approx(0.75)


def test_no_emoji_or_exclamation_in_labels_and_definitions():
    layer = build_default_semantic_layer()
    for key in layer.keys():
        d = layer.get(key)
        assert "!" not in d.label and "!" not in d.definition
        assert has_no_emoji(d.label) and has_no_emoji(d.definition)
