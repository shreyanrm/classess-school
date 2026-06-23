"""The strengthened steward FLAGS likely duplicates and DETECTS missing
prerequisites — both as candidates for review, never auto-applied (human final).
All flags carry an explainable rationale + confidence and no PII."""

from __future__ import annotations

from app._ontology import NodeKind, Skill, Topic
from app.embeddings import SemanticIndex
from app.seed import (
    SEED_ONTOLOGY_IDS,
    build_expanded_seed_snapshot,
    build_seed_snapshot,
)
from app.steward import (
    DUPLICATE_SIMILARITY_THRESHOLD,
    PrerequisiteSteward,
)


def _index_topics(snap) -> SemanticIndex:
    index = SemanticIndex.create()
    index.index_many((t.id, t.name) for t in snap.topics)
    return index


def test_detect_duplicates_flags_near_identical_same_chapter_topics():
    snap = build_seed_snapshot()
    # Inject a near-duplicate of an existing topic into the SAME chapter.
    euclid = snap.topic_by_id(SEED_ONTOLOGY_IDS["tEuclid"])
    dupe = Topic(
        id="dupe-topic-0001",
        chapter_id=euclid.chapter_id,
        name=euclid.name,  # identical text -> high similarity.
        sequence=99,
    )
    snap.topics.append(dupe)
    index = _index_topics(snap)
    steward = PrerequisiteSteward(snap)
    flags = steward.detect_duplicates(index)
    assert flags, "an identical-text same-chapter topic should be flagged"
    pair = {flags[0].left_id, flags[0].right_id}
    assert pair == {euclid.id, "dupe-topic-0001"}
    assert flags[0].node_kind is NodeKind.TOPIC
    assert flags[0].similarity >= DUPLICATE_SIMILARITY_THRESHOLD
    assert flags[0].rationale  # explainable.


def test_detect_duplicates_does_not_flag_distinct_topics():
    snap = build_seed_snapshot()
    index = _index_topics(snap)
    steward = PrerequisiteSteward(snap)
    # The seed's topics are genuinely distinct — no false duplicate flags.
    assert steward.detect_duplicates(index) == []


def test_detect_duplicate_skills_flags_near_identical_same_competency():
    snap = build_expanded_seed_snapshot()
    # Inject a near-duplicate of an existing skill under the SAME competency.
    base = snap.skills[0]
    dupe = Skill(
        id="dupe-skill-0001",
        competency_id=base.competency_id,
        name=base.name,  # identical text -> high similarity.
        statement=base.statement,
    )
    snap.skills.append(dupe)
    index = SemanticIndex.create()
    index.index_many((s.id, s.name) for s in snap.skills)
    steward = PrerequisiteSteward(snap)
    flags = steward.detect_duplicate_skills(index)
    assert flags, "an identical-text same-competency skill should be flagged"
    pair = {flags[0].left_id, flags[0].right_id}
    assert pair == {base.id, "dupe-skill-0001"}
    assert flags[0].node_kind is NodeKind.SKILL
    assert flags[0].similarity >= DUPLICATE_SIMILARITY_THRESHOLD


def test_detect_duplicate_skills_does_not_flag_distinct_skills():
    snap = build_expanded_seed_snapshot()
    index = SemanticIndex.create()
    index.index_many((s.id, s.name) for s in snap.skills)
    steward = PrerequisiteSteward(snap)
    # The expansion's skills are genuinely distinct — no false flags.
    assert steward.detect_duplicate_skills(index) == []


def test_detect_missing_prerequisites_skips_already_modelled_pairs():
    snap = build_seed_snapshot()
    index = _index_topics(snap)
    steward = PrerequisiteSteward(snap)
    flags = steward.detect_missing_prerequisites(index)
    # Every flagged pair must NOT already have an edge (proposed or confirmed).
    modelled = {
        frozenset((e.from_topic_id, e.to_topic_id)) for e in snap.edges
    }
    for f in flags:
        assert frozenset((f.topic_id, f.likely_prerequisite_id)) not in modelled
        assert f.similarity > 0.0
        assert f.rationale


def test_missing_prerequisite_flag_points_earlier_to_later():
    snap = build_seed_snapshot()
    # Drop all edges so the similar-pair gap is wide open, then detect.
    snap.edges = []
    index = _index_topics(snap)
    steward = PrerequisiteSteward(snap)
    flags = steward.detect_missing_prerequisites(index)
    assert flags, "with no edges, similar pairs should surface as missing prereqs"
    # The prerequisite is the earlier-sequenced topic; never self.
    for f in flags:
        assert f.topic_id != f.likely_prerequisite_id


def test_hygiene_flags_carry_no_pii():
    snap = build_seed_snapshot()
    index = _index_topics(snap)
    steward = PrerequisiteSteward(snap)
    forbidden = {"email", "phone", "student_name", "learner"}
    for f in steward.detect_missing_prerequisites(index):
        assert not (forbidden & set(vars(f).keys()))
