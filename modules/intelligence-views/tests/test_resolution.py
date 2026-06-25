"""Resolution surfacing: a resolved gap (the loop closing) is surfaced as a
plain-language, fully evidence-linked improvement — "what improved after the
last intervention". A resolution mints nothing and is derived purely by diffing
two governed profiles, so it agrees with the spine's gap.resolved emission.
"""

from __future__ import annotations

from app.resolution import (
    CohortImprovement,
    Improvement,
    detect_cohort_improvements,
    detect_improvements_for_learner,
)
from .conftest import LEARNER_A, T_TRIG_RATIOS, has_no_emoji

_LABELS = {T_TRIG_RATIOS: "Trigonometric ratios"}


def test_resolved_gap_is_surfaced_as_improvement(resolved_cohort):
    """The support-dependency gap confirmed before is gone after the intervention,
    so a diff surfaces exactly one improvement on the topic."""
    previous, current, topic_id = resolved_cohort
    prev_a = previous[0]
    cur_a = current[0]
    assert prev_a.subject == cur_a.subject == LEARNER_A
    imps = detect_improvements_for_learner(prev_a, cur_a, topic_labels=_LABELS)
    assert imps, "a gap that was confirmed before and is gone now must surface"
    by_type = {i.gap_type for i in imps}
    assert "support-dependency" in by_type


def test_improvement_carries_evidence_lineage(resolved_cohort):
    """No opaque claims: an improvement links the events that confirmed the gap
    AND the fresh evidence it resolved on."""
    previous, current, _ = resolved_cohort
    imps = detect_improvements_for_learner(previous[0], current[0], topic_labels=_LABELS)
    for imp in imps:
        assert imp.evidence_refs, "an improvement must link its evidence"
        for ref in imp.evidence_refs:
            assert ref.event_id is not None
            assert ref.summary
        assert imp.plain_language
        assert imp.why_am_i_seeing_this


def test_no_improvement_when_nothing_resolved(gap_cohort):
    """Diffing a profile against ITSELF surfaces nothing — the gap still stands,
    so there is no improvement to report (and no false good news)."""
    profiles, _ = gap_cohort
    imps = detect_improvements_for_learner(profiles[0], profiles[0], topic_labels=_LABELS)
    assert imps == []


def test_strong_cohort_has_no_prior_gap_so_no_improvement(strong_cohort):
    """A cohort that never had a confirmed gap cannot have a resolution — an
    improvement is only ever a gap that GOES, never an absence reframed."""
    profiles, _ = strong_cohort
    imps = detect_improvements_for_learner(profiles[0], profiles[0], topic_labels=_LABELS)
    assert imps == []


def test_cohort_improvement_rolls_up_with_count(resolved_cohort):
    """The briefing-level item rolls the resolution up across the cohort and
    carries how many learners it resolved for."""
    previous, current, topic_id = resolved_cohort
    cohort = detect_cohort_improvements(
        previous, current, cohort_label="Section 10-B", topic_labels=_LABELS
    )
    assert cohort
    item = cohort[0]
    assert isinstance(item, CohortImprovement)
    assert item.gap_type == "support-dependency"
    assert item.learner_count == 2  # both learners in the fixture resolved
    assert item.evidence_refs
    assert item.topic_id == topic_id


def test_cohort_improvements_ranked_most_learners_first(resolved_cohort):
    previous, current, _ = resolved_cohort
    cohort = detect_cohort_improvements(previous, current, topic_labels=_LABELS)
    counts = [c.learner_count for c in cohort]
    assert counts == sorted(counts, reverse=True)


def test_resolution_is_deterministic(resolved_cohort):
    previous, current, _ = resolved_cohort
    a = detect_cohort_improvements(previous, current, topic_labels=_LABELS)
    b = detect_cohort_improvements(previous, current, topic_labels=_LABELS)
    assert [(c.topic_id, c.gap_type, c.learner_count) for c in a] == [
        (c.topic_id, c.gap_type, c.learner_count) for c in b
    ]
    assert [c.plain_language for c in a] == [c.plain_language for c in b]


def test_improvement_without_evidence_is_refused():
    """A resolution surfaced without its lineage would be an opaque claim — the
    model refuses it, exactly as a dashboard alert refuses to surface without
    evidence."""
    import pytest

    with pytest.raises(ValueError):
        Improvement(
            label="A learner",
            topic_id=T_TRIG_RATIOS,
            topic_label="Trigonometric ratios",
            gap_type="support-dependency",
            plain_language="something improved",
            evidence_refs=[],  # no lineage
            confidence=0.8,
            why_am_i_seeing_this="why",
        )


def test_improvement_text_has_no_emoji_or_exclamation(resolved_cohort):
    previous, current, _ = resolved_cohort
    cohort = detect_cohort_improvements(previous, current, topic_labels=_LABELS)
    for c in cohort:
        for text in (c.plain_language, c.why_am_i_seeing_this):
            assert "!" not in text and has_no_emoji(text)
