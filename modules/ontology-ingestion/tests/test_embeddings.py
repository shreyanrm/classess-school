"""The semantic index: pgvector interface with a deterministic in-memory
fallback that works fully offline; Track 1 / Track 2 lanes kept separate."""

from __future__ import annotations

from app.config import OntologySettings
from app.embeddings import (
    HashingEmbedder,
    InMemoryVectorIndex,
    SemanticIndex,
    cosine,
    default_embedder,
    default_vector_index,
)


def test_defaults_are_offline_fallbacks_when_degraded():
    settings = OntologySettings()  # nothing configured.
    assert isinstance(default_embedder(settings), HashingEmbedder)
    assert isinstance(default_vector_index(settings), InMemoryVectorIndex)


def test_hashing_embedder_is_deterministic_and_normalised():
    emb = HashingEmbedder()
    v1 = emb.embed("Ohm's law and resistance")
    v2 = emb.embed("Ohm's law and resistance")
    assert v1 == v2                       # deterministic.
    assert len(v1) == emb.dim
    norm = sum(x * x for x in v1) ** 0.5
    assert abs(norm - 1.0) < 1e-9 or norm == 0.0  # L2-normalised.


def test_similar_text_ranks_itself_first():
    index = SemanticIndex.create(OntologySettings())
    pairs = [
        ("n-ohm", "Ohm's law and resistance"),
        ("n-resistors", "Resistors in series and parallel"),
        ("n-trig", "Trigonometric ratios of an acute angle"),
    ]
    index.index_many(pairs)
    hits = index.similar_to_text("Ohm's law and resistance", top_k=3)
    assert hits[0].node_id == "n-ohm"     # identical text ranks top.
    assert hits[0].score > hits[-1].score


def test_in_memory_index_upsert_is_idempotent():
    idx = InMemoryVectorIndex()
    idx.upsert("n1", [1.0, 0.0])
    idx.upsert("n1", [0.0, 1.0])          # overwrite, not duplicate.
    assert len(idx) == 1


def test_cosine_handles_zero_and_mismatch_without_raising():
    assert cosine([], []) == 0.0
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    # Mismatched lengths compare the shared prefix rather than raising.
    assert cosine([1.0, 0.0, 5.0], [1.0, 0.0]) == 1.0


def test_track_lanes_are_separate_in_settings():
    # Track 1 (external) and Track 2 (edge) keys are DISTINCT fields; configuring
    # one does not configure the other — they are never blended.
    s1 = OntologySettings(gateway_url="g", embeddings_track1_key="t1")
    s2 = OntologySettings(gateway_url="g", embeddings_track2_key="t2")
    assert s1.embeddings_track1_key == "t1" and s1.embeddings_track2_key is None
    assert s2.embeddings_track2_key == "t2" and s2.embeddings_track1_key is None
    # Either lane alone is enough to consider live embeddings available.
    assert s1.has_embeddings is True
    assert s2.has_embeddings is True


def test_semantic_index_reports_degraded_offline():
    index = SemanticIndex.create(OntologySettings())
    assert index.degraded is True
