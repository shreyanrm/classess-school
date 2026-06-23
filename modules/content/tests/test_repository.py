"""Repository: versioning, approval lifecycle, licence, semantic search."""

import content
from content.repository import (
    ApprovalState,
    ApprovalTransitionError,
    ContentKind,
    InMemoryContentRepository,
    InMemorySemanticSearchIndex,
    LicenceMetadata,
    PgVectorSearchIndex,
    env_var_name,
)

import pytest


def _repo() -> InMemoryContentRepository:
    return InMemoryContentRepository()


def _verified_record(repo):
    return repo.create(
        topic_id="topic-1",
        kind=ContentKind.WORKED_EXAMPLE,
        title="Worked example A",
        body={"answer": 42},
        licence=LicenceMetadata.for_generated(),
        author="system:generate",
        verified_served=True,
    )


def test_create_is_draft_and_not_servable():
    repo = _repo()
    rec = _verified_record(repo)
    assert rec.approval_state is ApprovalState.DRAFT
    assert rec.live_version_id is None
    assert rec.is_servable is False
    assert rec.latest_version.number == 1


def test_versioning_appends_immutable_history():
    repo = _repo()
    rec = _verified_record(repo)
    v1_id = rec.latest_version.version_id
    rec2 = repo.add_version(rec.content_id, body={"answer": 43}, author="user:teacher", verified_served=True)
    assert len(rec2.versions) == 2
    assert rec2.versions[0].version_id == v1_id  # history preserved, not rewritten
    assert rec2.versions[0].body == {"answer": 42}
    assert rec2.latest_version.number == 2


def test_approval_promotes_verified_version_to_live_and_servable():
    repo = _repo()
    rec = _verified_record(repo)
    repo.transition(rec.content_id, ApprovalState.IN_REVIEW)
    approved = repo.transition(rec.content_id, ApprovalState.APPROVED)
    assert approved.approval_state is ApprovalState.APPROVED
    assert approved.live_version is not None
    assert approved.is_servable is True


def test_cannot_approve_unverified_version():
    repo = _repo()
    rec = repo.create(
        topic_id="topic-1", kind=ContentKind.DOCUMENT, title="ingested",
        body={"text": ""}, licence=LicenceMetadata.for_generated(),
        author="ingest", verified_served=False,
    )
    repo.transition(rec.content_id, ApprovalState.IN_REVIEW)
    with pytest.raises(ApprovalTransitionError):
        repo.transition(rec.content_id, ApprovalState.APPROVED)


def test_illegal_transition_rejected():
    repo = _repo()
    rec = _verified_record(repo)
    with pytest.raises(ApprovalTransitionError):
        repo.transition(rec.content_id, ApprovalState.APPROVED)  # DRAFT -> APPROVED not allowed


def test_new_version_after_approval_returns_to_review_and_withdraws_live():
    repo = _repo()
    rec = _verified_record(repo)
    repo.transition(rec.content_id, ApprovalState.IN_REVIEW)
    repo.transition(rec.content_id, ApprovalState.APPROVED)
    updated = repo.add_version(rec.content_id, body={"answer": 44}, author="user:teacher", verified_served=True)
    assert updated.approval_state is ApprovalState.IN_REVIEW
    assert updated.live_version_id is None
    assert updated.is_servable is False


def test_for_topic_only_servable_filter():
    repo = _repo()
    rec = _verified_record(repo)
    repo.transition(rec.content_id, ApprovalState.IN_REVIEW)
    repo.transition(rec.content_id, ApprovalState.APPROVED)
    repo.create(
        topic_id="topic-1", kind=ContentKind.EXPLANATION, title="draft only",
        body={}, licence=LicenceMetadata.for_generated(), author="system:generate",
        verified_served=True,
    )
    all_for_topic = repo.for_topic("topic-1")
    servable = repo.for_topic("topic-1", only_servable=True)
    assert len(all_for_topic) == 2
    assert len(servable) == 1
    assert servable[0].content_id == rec.content_id


def test_semantic_search_in_memory_cosine_and_servable_filter():
    repo = _repo()
    rec = _verified_record(repo)
    repo.transition(rec.content_id, ApprovalState.IN_REVIEW)
    repo.transition(rec.content_id, ApprovalState.APPROVED)
    draft = repo.create(
        topic_id="topic-1", kind=ContentKind.EXPLANATION, title="draft",
        body={}, licence=LicenceMetadata.for_generated(), author="system:generate",
        verified_served=True,
    )
    repo.index_vector(rec.content_id, [1.0, 0.0, 0.0])
    repo.index_vector(draft.content_id, [1.0, 0.0, 0.0])

    # Default only_servable=True hides the draft.
    hits = repo.search([1.0, 0.0, 0.0], top_k=5)
    ids = {h.content_id for h in hits}
    assert rec.content_id in ids
    assert draft.content_id not in ids

    # Including drafts surfaces both.
    hits_all = repo.search([1.0, 0.0, 0.0], top_k=5, only_servable=False)
    assert len(hits_all) == 2
    assert all(0.0 <= h.score <= 1.0 for h in hits_all)


def test_semantic_index_topic_filter():
    idx = InMemorySemanticSearchIndex()
    idx.upsert("a", "topic-1", [1.0, 0.0])
    idx.upsert("b", "topic-2", [1.0, 0.0])
    hits = idx.query([1.0, 0.0], topic_id="topic-1")
    assert [h.content_id for h in hits] == ["a"]


def test_pgvector_index_reports_unavailable_without_connection():
    idx = PgVectorSearchIndex()
    assert idx.available is False
    with pytest.raises(RuntimeError):
        idx.query([1.0, 0.0])


def test_licence_for_generated_marks_machine_generated():
    lic = LicenceMetadata.for_generated()
    assert lic.machine_generated is True
    assert lic.source == "generated"


def test_env_var_name_mapping():
    assert env_var_name("clss.content.dev.pgvector_dsn") == "CLSS_CONTENT_DEV_PGVECTOR_DSN"
