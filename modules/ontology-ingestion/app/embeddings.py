"""Semantic index for ontology nodes (A2, Ring 1).

A pgvector-backed semantic index INTERFACE with a deterministic in-memory
fallback, so the pipeline runs fully offline. Two collaborating Protocols:

  - :class:`Embedder` — turns a node's text into a vector. The live embedder
    calls a model provider THROUGH the gateway. TRACK SEPARATION: the external
    (Track 1) and proprietary/edge (Track 2) model lanes are NAMED in separate
    env vars and selected by a router; this module never blends their keys.
  - :class:`VectorIndex` — stores vectors and answers nearest-neighbour queries.
    The live index is pgvector; the fallback is :class:`InMemoryVectorIndex`
    (exact cosine over a Python list — correct, just not scaled).

Degrades gracefully: with no gateway + provider key, :func:`default_embedder`
returns :class:`HashingEmbedder` — a deterministic, offline, dependency-free
embedder (a hashed bag-of-tokens projection). It is NOT a real semantic model;
it is a stable stand-in so the index, similarity queries, and the steward's
proposal heuristic all work and stay testable without a network. The env var
NAMES the live path reads are referenced here, never read for a value.

No PII: a node vector is derived only from the node's curriculum text (name /
statement) and stored against its opaque node id. Behavioural data never enters
this index.

Import-safe: pure-Python math, no third-party import, no I/O at import.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable

from .config import (
    ENV_EMBEDDINGS_TRACK1_KEY,
    ENV_EMBEDDINGS_TRACK2_KEY,
    ENV_PGVECTOR_URL,
    OntologySettings,
    get_settings,
)


# Dimensionality of the fallback hashing embedder. Small + fixed: deterministic
# and cheap. A live model would set its own dimensionality.
FALLBACK_DIM = 64


@runtime_checkable
class Embedder(Protocol):
    """Turns text into a fixed-length vector."""

    dim: int
    provider: str

    def embed(self, text: str) -> list[float]: ...


@runtime_checkable
class VectorIndex(Protocol):
    """Stores node vectors and answers nearest-neighbour queries by node id."""

    def upsert(self, node_id: str, vector: list[float]) -> None: ...

    def query(self, vector: list[float], *, top_k: int = 5) -> list["SimilarityHit"]: ...

    def __len__(self) -> int: ...


@dataclass(frozen=True)
class SimilarityHit:
    """One nearest-neighbour result."""

    node_id: str
    score: float  # cosine similarity in [-1, 1]; 1.0 == identical direction.


def _tokenize(text: str) -> list[str]:
    out: list[str] = []
    token: list[str] = []
    for ch in text.lower():
        if ch.isalnum():
            token.append(ch)
        elif token:
            out.append("".join(token))
            token = []
    if token:
        out.append("".join(token))
    return out


class HashingEmbedder:
    """Deterministic, offline embedder (the degraded default).

    Projects a bag of tokens into a fixed-dimensional vector by hashing each
    token to a bucket with a signed weight, then L2-normalises. Deterministic,
    dependency-free, and stable across runs — a stand-in for a real model so the
    semantic index and similarity heuristics work without a network. NOT a real
    semantic embedding; clearly labelled as such.
    """

    provider = "hashing-fallback"

    def __init__(self, dim: int = FALLBACK_DIM) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _tokenize(text):
            h = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = h[0] % self.dim
            sign = 1.0 if (h[1] & 1) == 0 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            return vec
        return [v / norm for v in vec]


def default_embedder(settings: OntologySettings | None = None) -> Embedder:
    """Select the embedder.

    With no gateway + a model-lane key configured, returns the deterministic
    :class:`HashingEmbedder`. A live embedder would be returned when a lane is
    configured; it is intentionally not implemented while no provider exists.
    TRACK SEPARATION is preserved: a live build picks the Track 1 OR Track 2 key
    by router policy and never blends them.
    """
    settings = settings or get_settings()
    if not settings.has_embeddings:
        return HashingEmbedder()
    raise NotImplementedError(
        "A live embeddings lane is configured but not wired. Implement an "
        "Embedder that calls the chosen model lane through the gateway — Track 1 "
        f"({ENV_EMBEDDINGS_TRACK1_KEY}) and Track 2 ({ENV_EMBEDDINGS_TRACK2_KEY}) "
        "are SEPARATE keys selected by router policy and never blended. Until "
        "then leave the lane keys unset to use the hashing fallback."
    )


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors. 0.0 if either is
    zero-length. Defensive: pads/truncates to the shorter length so a dimension
    mismatch never raises (it degrades to comparing the shared prefix)."""
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(a[i] * a[i] for i in range(n)))
    nb = math.sqrt(sum(b[i] * b[i] for i in range(n)))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class InMemoryVectorIndex:
    """Exact in-memory nearest-neighbour index (the pgvector fallback).

    Stores ``node_id -> vector`` and answers cosine queries by brute force.
    Correct and deterministic; not scaled — the live path is pgvector. Upsert is
    idempotent on node id.
    """

    provider = "in-memory"

    def __init__(self) -> None:
        self._vectors: dict[str, list[float]] = {}

    def upsert(self, node_id: str, vector: list[float]) -> None:
        self._vectors[node_id] = list(vector)

    def query(self, vector: list[float], *, top_k: int = 5) -> list[SimilarityHit]:
        hits = [
            SimilarityHit(node_id=nid, score=cosine(vector, vec))
            for nid, vec in self._vectors.items()
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[: max(0, top_k)]

    def __len__(self) -> int:
        return len(self._vectors)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self._vectors


def default_vector_index(settings: OntologySettings | None = None) -> VectorIndex:
    """Select the vector index.

    With no gateway + pgvector URL configured, returns the in-memory fallback. A
    live pgvector index would be returned when configured; not implemented while
    no provider exists — the Protocol is the contract.
    """
    settings = settings or get_settings()
    if not settings.has_pgvector:
        return InMemoryVectorIndex()
    raise NotImplementedError(
        "A pgvector index is configured but not wired. Implement a VectorIndex "
        f"backed by pgvector at {ENV_PGVECTOR_URL} (reached through the gateway). "
        "Until then leave the pgvector URL unset to use the in-memory index."
    )


@dataclass
class SemanticIndex:
    """An embedder + a vector index, with node-text convenience.

    The pipeline indexes ontology nodes by their curriculum text and queries by
    text. Both halves degrade independently; the default is fully offline.
    """

    embedder: Embedder
    index: VectorIndex

    @classmethod
    def create(cls, settings: OntologySettings | None = None) -> "SemanticIndex":
        settings = settings or get_settings()
        return cls(
            embedder=default_embedder(settings),
            index=default_vector_index(settings),
        )

    @property
    def degraded(self) -> bool:
        return getattr(self.index, "provider", "") == "in-memory" or \
            getattr(self.embedder, "provider", "") == "hashing-fallback"

    def index_node(self, node_id: str, text: str) -> list[float]:
        """Embed a node's curriculum text and store it by opaque node id."""
        vector = self.embedder.embed(text)
        self.index.upsert(node_id, vector)
        return vector

    def index_many(self, items: Iterable[tuple[str, str]]) -> int:
        """Index ``(node_id, text)`` pairs. Returns the count indexed."""
        count = 0
        for node_id, text in items:
            self.index_node(node_id, text)
            count += 1
        return count

    def similar_to_text(self, text: str, *, top_k: int = 5) -> list[SimilarityHit]:
        return self.index.query(self.embedder.embed(text), top_k=top_k)

    def __len__(self) -> int:
        return len(self.index)
