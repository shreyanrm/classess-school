"""Learning-outcome coverage is computed structurally (outcome → skill →
question), surfaces uncovered outcomes as gaps, and curriculum versioning selects
the version effective on a date and exposes the supersession chain."""

from __future__ import annotations

from app._ontology import (
    CurriculumVersion,
    NodeKind,
    Question,
    Skill,
)
from app.coverage import (
    competency_coverage,
    effective_version,
    outcome_coverage,
    supersession_chain,
    versions_for_scope,
)
from app.seed import (
    SEED_ONTOLOGY_IDS,
    build_expanded_seed_snapshot,
    build_seed_snapshot,
)


def test_uncovered_outcomes_are_flagged_as_gaps():
    # The canonical seed has outcomes but no questions — everything uncovered.
    snap = build_seed_snapshot()
    report = outcome_coverage(snap)
    assert report.total == len(snap.outcomes)
    assert report.coverage_ratio == 0.0
    assert len(report.uncovered) == report.total
    assert report.covered == []


def test_covered_outcome_traces_to_a_question_through_a_skill():
    snap = build_expanded_seed_snapshot()
    report = outcome_coverage(snap, subject_id=SEED_ONTOLOGY_IDS["subjMath"])
    covered = {i.outcome_id: i for i in report.covered}
    # The Euclid outcome is reached via skill skHcf -> question qHcf.
    euclid = SEED_ONTOLOGY_IDS["outcomes"]["euclid"]
    assert euclid in covered
    item = covered[euclid]
    assert item.covered is True
    assert item.question_ids  # explainability: the evidence questions.
    assert 0.0 < report.coverage_ratio <= 1.0


def test_coverage_counts_a_direct_question_outcome_link():
    snap = build_seed_snapshot()
    euclid = SEED_ONTOLOGY_IDS["outcomes"]["euclid"]
    # A question linked DIRECTLY to an outcome (no skill) still covers it.
    snap.skills.append(
        Skill(id="s-1", competency_id=SEED_ONTOLOGY_IDS["compNumberReasoning"],
              name="x", statement="x")
    )
    snap.questions.append(
        Question(id="q-1", skill_id="s-1", stem="q", outcome_id=euclid)
    )
    report = outcome_coverage(snap)
    item = next(i for i in report.items if i.outcome_id == euclid)
    assert item.covered is True
    assert "q-1" in item.question_ids


def test_competency_coverage_rolls_outcomes_up_to_status():
    snap = build_expanded_seed_snapshot()
    rollup = {c.competency_id: c for c in competency_coverage(snap)}
    # Number reasoning lists euclid, fundThm, irrational. The expansion backs
    # euclid + fundThm with questions but not irrational -> partial.
    number = rollup[SEED_ONTOLOGY_IDS["compNumberReasoning"]]
    assert number.status == "partial"
    euclid = SEED_ONTOLOGY_IDS["outcomes"]["euclid"]
    irrational = SEED_ONTOLOGY_IDS["outcomes"]["irrational"]
    assert euclid in number.covered_ids
    assert irrational in number.uncovered_ids
    assert 0.0 < number.coverage_ratio < 1.0


def test_competency_with_no_assessable_content_is_none():
    snap = build_seed_snapshot()  # no questions at all -> nothing covered.
    rollup = competency_coverage(snap)
    assert rollup, "every competency should appear in the rollup"
    assert all(c.status == "none" for c in rollup)


def test_competency_coverage_filters_by_subject():
    snap = build_expanded_seed_snapshot()
    maths = competency_coverage(snap, subject_id=SEED_ONTOLOGY_IDS["subjMath"])
    phys = competency_coverage(snap, subject_id=SEED_ONTOLOGY_IDS["subjPhys"])
    maths_ids = {c.competency_id for c in maths}
    phys_ids = {c.competency_id for c in phys}
    assert SEED_ONTOLOGY_IDS["compNumberReasoning"] in maths_ids
    assert SEED_ONTOLOGY_IDS["compGeomOptics"] in phys_ids
    assert maths_ids.isdisjoint(phys_ids)


def test_effective_version_picks_latest_on_or_before_date():
    snap = build_expanded_seed_snapshot()
    subj = SEED_ONTOLOGY_IDS["subjMath"]
    assert len(versions_for_scope(snap, subj)) == 2
    # Before any version takes effect -> None.
    assert effective_version(snap, subj, on_date="2022-01-01") is None
    # Between the two revisions -> the older one.
    v_2023 = effective_version(snap, subj, on_date="2023-06-01")
    assert v_2023 is not None and v_2023.version == "2023.1"
    # After the refresh -> the newer one.
    v_2024 = effective_version(snap, subj, on_date="2025-01-01")
    assert v_2024 is not None and v_2024.version == "2024.1"


def test_supersession_chain_is_oldest_first_and_linear():
    snap = build_expanded_seed_snapshot()
    subj = SEED_ONTOLOGY_IDS["subjMath"]
    chain = supersession_chain(snap, subj)
    assert [v.version for v in chain] == ["2023.1", "2024.1"]
    # The newer supersedes the older.
    assert chain[1].supersedes_id == chain[0].id


def test_versioning_is_scope_isolated():
    snap = build_expanded_seed_snapshot()
    # A scope with no version stamps returns nothing — no cross-scope leakage.
    assert versions_for_scope(snap, SEED_ONTOLOGY_IDS["subjPhys"]) == []
    assert effective_version(snap, SEED_ONTOLOGY_IDS["subjPhys"], on_date="2025-01-01") is None
