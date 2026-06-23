"""Tests for the retrieval hook. Import-safe, no network."""

from __future__ import annotations

from app.retrieval import NullRetriever, RetrievedContext, StaticRetriever


def test_null_retriever_returns_nothing():
    r = NullRetriever()
    assert r.retrieve(query="anything", task_class="t") == []


def _corpus():
    return [
        RetrievedContext("c1", "fractions add denominators must match"),
        RetrievedContext("c2", "photosynthesis converts light into energy"),
        RetrievedContext("c3", "adding fractions with common denominators"),
    ]


def test_static_retriever_ranks_by_overlap():
    r = StaticRetriever(corpus=_corpus())
    out = r.retrieve(query="adding fractions", task_class="t", k=2)
    ids = [c.source_id for c in out]
    # Both fraction snippets match; the unrelated one does not.
    assert "c2" not in ids
    assert set(ids) <= {"c1", "c3"}
    # Scores are descending.
    assert out[0].score >= out[-1].score


def test_static_retriever_no_overlap_returns_empty():
    r = StaticRetriever(corpus=_corpus())
    assert r.retrieve(query="quantum chromodynamics", task_class="t") == []


def test_static_retriever_empty_query_returns_empty():
    r = StaticRetriever(corpus=_corpus())
    assert r.retrieve(query="", task_class="t") == []
    assert r.retrieve(query="fractions", task_class="t", k=0) == []
