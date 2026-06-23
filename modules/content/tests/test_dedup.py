"""Tests for content.dedup: near-duplicate detection, no network/DB/keys."""

from __future__ import annotations

import os
import sys

import pytest

# Make the module importable whether pytest's rootdir is the repo, the module,
# or the tests dir. No network, DB or keys are touched.
_MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

import dedup  # noqa: E402
from dedup import (  # noqa: E402
    ContentItem,
    DedupIndex,
    DuplicateKind,
    compare,
    content_hash,
    find_duplicates,
    is_duplicate,
    jaccard,
    normalise,
    semantic_similarity,
)


def test_module_import_safe():
    assert hasattr(dedup, "find_duplicates")


def test_normalise_collapses_case_punctuation_whitespace():
    assert normalise("The   Quick, Brown FOX!") == "the quick brown fox"


def test_exact_duplicate_via_hash():
    a = ContentItem("c1", "Photosynthesis converts light to energy.")
    b = ContentItem("c2", "photosynthesis  converts LIGHT to energy!!!")
    assert a.hash == b.hash
    kind, score = compare(a, b)
    assert kind is DuplicateKind.EXACT
    assert score == 1.0


def test_near_hash_duplicate_small_edit():
    a = ContentItem(
        "c1",
        "Photosynthesis is the process by which green plants convert sunlight "
        "into chemical energy stored as sugar",
    )
    b = ContentItem(
        "c2",
        "Photosynthesis is the process by which green plants convert sunlight "
        "into chemical energy stored as glucose",
    )
    kind, score = compare(a, b)
    assert kind is DuplicateKind.NEAR_HASH
    assert 0.82 <= score < 1.0
    assert content_hash(a.text) != content_hash(b.text)


def test_near_semantic_paraphrase_with_embedder():
    # Hash-distinct paraphrases; an injected embedder makes them semantically close.
    a = ContentItem("c1", "A triangle has three sides")
    b = ContentItem("c2", "Every three-sided polygon is called a triangle")

    vecs = {
        f"{a.title} {a.text}": [1.0, 0.0, 1.0],
        f"{b.title} {b.text}": [0.98, 0.05, 0.97],
    }

    def embedder(text):
        return vecs[text]

    # lexical jaccard alone should NOT trip the near-hash threshold here
    assert jaccard(a.text, b.text) < 0.82
    kind, score = compare(a, b, embedder=embedder)
    assert kind is DuplicateKind.NEAR_SEMANTIC
    assert score >= 0.86


def test_unique_content_not_flagged():
    a = ContentItem("c1", "The mitochondria is the powerhouse of the cell")
    b = ContentItem("c2", "Shakespeare wrote many tragedies and comedies")
    kind, _ = compare(a, b)
    assert kind is DuplicateKind.UNIQUE


def test_find_duplicates_returns_advisory_verdicts():
    corpus = [
        ContentItem("a", "The sun is a star at the centre of the solar system"),
        ContentItem("b", "Plants need sunlight water and carbon dioxide to grow"),
    ]
    candidate = ContentItem(
        "c", "the SUN is a star, at the centre of the solar system."
    )
    verdicts = find_duplicates(candidate, corpus)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.match_id == "a"
    # Removal is consequential -> never auto-fired (permission ladder).
    assert v.requires_human_approval is True


def test_find_duplicates_skips_self():
    item = ContentItem("x", "some unique sentence about gravity and orbits today")
    assert find_duplicates(item, [item]) == []


def test_is_duplicate_predicate():
    corpus = [ContentItem("a", "Magnets have a north pole and a south pole")]
    dup = ContentItem("b", "magnets have a NORTH pole and a south pole")
    assert is_duplicate(dup, corpus) is True
    assert is_duplicate(ContentItem("c", "Rivers flow toward the ocean"), corpus) is False


def test_semantic_falls_back_to_lexical_without_embedder():
    s = semantic_similarity("the cat sat on the mat", "the cat sat on the mat")
    assert s == pytest.approx(1.0)
    assert semantic_similarity("apples", "quantum physics") == 0.0


def test_dedup_index_keeps_canonical_set_clean():
    idx = DedupIndex()
    assert idx.add(ContentItem("1", "Gravity pulls objects toward the earth")) == []
    # near-duplicate of item 1 -> flagged, not stored
    verdicts = idx.add(ContentItem("2", "gravity pulls objects toward the EARTH!"))
    assert verdicts and verdicts[0].kind is DuplicateKind.EXACT
    assert len(idx.items) == 1
    # genuinely new -> stored
    assert idx.add(ContentItem("3", "Friction opposes the motion of surfaces")) == []
    assert len(idx.items) == 2


def test_embedder_failure_degrades_gracefully():
    def broken(_text):
        raise RuntimeError("no gateway")

    # Should not raise; falls back to lexical similarity.
    score = semantic_similarity("ABCDEF", "ABCDEF", embedder=broken)
    assert score == pytest.approx(1.0)
