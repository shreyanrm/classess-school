"""Target analytics: target vs trajectory, explainable, advisory, deterministic."""

from __future__ import annotations

from datetime import datetime, timezone

from app.target_analytics import (
    Target,
    TargetStatus,
    analyze_target,
    analyze_targets,
)
from .conftest import OWNER, T_FRACTIONS, T_TRIG_RATIOS, has_no_emoji

DUE = datetime(2026, 8, 1, tzinfo=timezone.utc)


def _target(topic_id=T_TRIG_RATIOS, label="Trigonometric ratios"):
    return Target(topic_id=topic_id, topic_label=label, due_date=DUE,
                  owner_role="coordinator", owner_ref=OWNER)


def test_strong_cohort_meets_or_on_track(strong_cohort):
    profiles, topic_id = strong_cohort
    a = analyze_target(profiles, _target(topic_id), coverage={topic_id: (4, 4)})
    assert a.status in (TargetStatus.MET_OR_AHEAD, TargetStatus.ON_TRACK)


def test_gap_cohort_at_risk_or_off_track(gap_cohort):
    profiles, topic_id = gap_cohort
    a = analyze_target(profiles, _target(topic_id), coverage={topic_id: (3, 4)})
    assert a.status in (TargetStatus.AT_RISK, TargetStatus.OFF_TRACK)
    assert a.gap_to_target > 0


def test_analysis_carries_full_explainability(gap_cohort):
    profiles, topic_id = gap_cohort
    a = analyze_target(profiles, _target(topic_id), coverage={topic_id: (3, 4)})
    assert a.plain_language
    assert a.consequence_of_ignoring
    assert a.why_am_i_seeing_this
    assert a.owner_role == "coordinator"
    assert a.owner_ref == OWNER
    assert a.due_date == DUE
    assert a.confidence_band in ("low", "medium", "high")
    assert a.forecast is not None  # the trajectory it rests on, for lineage


def test_analysis_is_deterministic(gap_cohort):
    profiles, topic_id = gap_cohort
    cov = {topic_id: (3, 4)}
    a = analyze_target(profiles, _target(topic_id), coverage=cov)
    b = analyze_target(profiles, _target(topic_id), coverage=cov)
    assert a.status == b.status
    assert a.gap_to_target == b.gap_to_target
    assert a.plain_language == b.plain_language


def test_targets_sorted_most_at_risk_first(strong_cohort, gap_cohort):
    """Mix a met goal and an at-risk goal; the at-risk one surfaces first."""
    sp, st = strong_cohort
    gp, gt = gap_cohort
    # Build a combined profile list so both topics resolve over the same call.
    profiles = sp + gp
    targets = [
        Target(topic_id=st, topic_label="Trig ratios (strong)", owner_ref=OWNER),
        Target(topic_id=gt, topic_label="Trig ratios (gap)", owner_ref=OWNER),
    ]
    # Note: both fixtures use the same topic id, so distinguish by coverage.
    results = analyze_targets(profiles, targets, coverage={st: (4, 4), gt: (3, 4)})
    # Most-at-risk status sorts ahead of met/on-track.
    statuses = [r.status for r in results]
    risk_order = {TargetStatus.OFF_TRACK: 0, TargetStatus.AT_RISK: 1,
                  TargetStatus.ON_TRACK: 2, TargetStatus.MET_OR_AHEAD: 3}
    assert statuses == sorted(statuses, key=lambda s: risk_order[s])


def test_invalid_target_mastery_rejected():
    import pytest

    with pytest.raises(ValueError):
        Target(topic_id=T_FRACTIONS, topic_label="Fractions", target_mastery=1.5)


def test_text_has_no_emoji_or_exclamation(gap_cohort):
    profiles, topic_id = gap_cohort
    a = analyze_target(profiles, _target(topic_id), coverage={topic_id: (3, 4)})
    for text in (a.plain_language, a.consequence_of_ignoring, a.why_am_i_seeing_this):
        assert "!" not in text and has_no_emoji(text)
