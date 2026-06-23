"""Content deduplication by semantic + hash similarity.

Catches three classes of duplicate so the catalog stays clean:

  1. EXACT      - byte/normalised-text identical (content hash match).
  2. NEAR_HASH  - small edits, reorderings, whitespace/markup churn
                  (token-shingle MinHash / Jaccard over normalised text).
  3. NEAR_SEMANTIC - paraphrases that hash-diff but mean the same thing
                  (cosine over an embedding supplied by the ai-fabric gateway,
                  with an offline lexical fallback when no embedder is wired).

Invariant notes (02-laws-altitude-principles-security.md):

  * PII-free: items are referenced by opaque ``content_id``; this module never
    requires names or e-mails. Free text is *content* (titles/bodies), not
    identity.
  * Gateway: semantic similarity uses a caller-injected embedder that, in
    production, routes through the ai-fabric gateway (secrets ENV-ONLY,
    clss.content.<env>.fabric_key, read by the gateway, never here). With no
    embedder the module degrades gracefully to lexical similarity.
  * Permission ladder: deduplication only *flags* duplicates. Removing or
    merging catalog content is a consequential action and is NOT auto-fired;
    callers receive a :class:`DuplicateVerdict` to route for human approval.
  * Deterministic + offline: no network, DB, or live keys required.

Import-safe and dependency-free (standard library only).
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Tunables (non-secret; safe as plain config / env if a deployment overrides)
# ---------------------------------------------------------------------------

DEFAULT_NEAR_HASH_THRESHOLD = 0.82   # Jaccard over shingles
DEFAULT_SEMANTIC_THRESHOLD = 0.86    # cosine over embeddings
SHINGLE_SIZE = 3                     # word k-shingles


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def normalise(text: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace.

    Stable across markup churn, casing and spacing so trivial edits collapse to
    the same normalised form for hashing.
    """

    if not text:
        return ""
    low = text.lower()
    low = _PUNCT_RE.sub(" ", low)
    return _WS_RE.sub(" ", low).strip()


def content_hash(text: str) -> str:
    """Stable hash of the normalised text (exact-duplicate key)."""

    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Lexical (hash) similarity
# ---------------------------------------------------------------------------


def _shingles(text: str, k: int = SHINGLE_SIZE) -> set:
    words = normalise(text).split()
    if len(words) < k:
        # short texts: fall back to the word set so they can still match
        return set(words)
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def jaccard(a: str, b: str, k: int = SHINGLE_SIZE) -> float:
    """Jaccard similarity of word k-shingles, 0..1."""

    sa, sb = _shingles(a, k), _shingles(b, k)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


# ---------------------------------------------------------------------------
# Semantic similarity
# ---------------------------------------------------------------------------

# An embedder maps text -> a fixed-length vector. The production embedder
# routes through the ai-fabric gateway; secrets stay in ENV and are read there.
Embedder = Callable[[str], Sequence[float]]


def cosine(u: Sequence[float], v: Sequence[float]) -> float:
    if not u or not v or len(u) != len(v):
        return 0.0
    dot = sum(x * y for x, y in zip(u, v))
    nu = math.sqrt(sum(x * x for x in u))
    nv = math.sqrt(sum(y * y for y in v))
    if nu == 0 or nv == 0:
        return 0.0
    return dot / (nu * nv)


def _lexical_vector(text: str) -> Dict[str, float]:
    """Offline fallback "embedding": bag-of-words term frequency."""

    vec: Dict[str, float] = {}
    for w in normalise(text).split():
        vec[w] = vec.get(w, 0.0) + 1.0
    return vec


def _sparse_cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[w] * b[w] for w in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def semantic_similarity(
    a: str, b: str, embedder: Optional[Embedder] = None
) -> float:
    """Cosine similarity in embedding space, or lexical cosine offline."""

    if embedder is not None:
        try:
            return cosine(list(embedder(a)), list(embedder(b)))
        except Exception:
            pass  # degrade gracefully to lexical fallback
    return _sparse_cosine(_lexical_vector(a), _lexical_vector(b))


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class DuplicateKind(str, Enum):
    EXACT = "exact"
    NEAR_HASH = "near_hash"
    NEAR_SEMANTIC = "near_semantic"
    UNIQUE = "unique"


@dataclass(frozen=True)
class ContentItem:
    """A catalog item referenced by an opaque id. PII-free."""

    content_id: str
    text: str
    title: str = ""

    @property
    def hash(self) -> str:
        return content_hash(f"{self.title}\n{self.text}")


@dataclass(frozen=True)
class DuplicateVerdict:
    """A flagged candidate duplicate. ADVISORY ONLY.

    Per the permission ladder, removal/merge is consequential and is never
    auto-fired from this verdict; it routes to human approval.
    """

    candidate_id: str
    match_id: str
    kind: DuplicateKind
    score: float
    requires_human_approval: bool = True


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def compare(
    a: ContentItem,
    b: ContentItem,
    *,
    embedder: Optional[Embedder] = None,
    near_hash_threshold: float = DEFAULT_NEAR_HASH_THRESHOLD,
    semantic_threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
) -> Tuple[DuplicateKind, float]:
    """Classify the relationship between two items.

    Returns (kind, score). Order of precedence: exact, then near-hash, then
    near-semantic, else unique.
    """

    if a.hash == b.hash:
        return DuplicateKind.EXACT, 1.0

    j = jaccard(f"{a.title} {a.text}", f"{b.title} {b.text}")
    if j >= near_hash_threshold:
        return DuplicateKind.NEAR_HASH, j

    s = semantic_similarity(
        f"{a.title} {a.text}", f"{b.title} {b.text}", embedder=embedder
    )
    if s >= semantic_threshold:
        return DuplicateKind.NEAR_SEMANTIC, s

    return DuplicateKind.UNIQUE, max(j, s)


def find_duplicates(
    candidate: ContentItem,
    corpus: Sequence[ContentItem],
    *,
    embedder: Optional[Embedder] = None,
    near_hash_threshold: float = DEFAULT_NEAR_HASH_THRESHOLD,
    semantic_threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
) -> List[DuplicateVerdict]:
    """Flag every corpus item the candidate duplicates.

    Verdicts are advisory and carry ``requires_human_approval=True``.
    """

    verdicts: List[DuplicateVerdict] = []
    for other in corpus:
        if other.content_id == candidate.content_id:
            continue
        kind, score = compare(
            candidate,
            other,
            embedder=embedder,
            near_hash_threshold=near_hash_threshold,
            semantic_threshold=semantic_threshold,
        )
        if kind is not DuplicateKind.UNIQUE:
            verdicts.append(
                DuplicateVerdict(
                    candidate_id=candidate.content_id,
                    match_id=other.content_id,
                    kind=kind,
                    score=round(score, 4),
                )
            )
    # strongest matches first
    verdicts.sort(key=lambda v: v.score, reverse=True)
    return verdicts


def is_duplicate(
    candidate: ContentItem,
    corpus: Sequence[ContentItem],
    *,
    embedder: Optional[Embedder] = None,
    near_hash_threshold: float = DEFAULT_NEAR_HASH_THRESHOLD,
    semantic_threshold: float = DEFAULT_SEMANTIC_THRESHOLD,
) -> bool:
    """Convenience predicate: does the candidate duplicate anything in corpus?"""

    return bool(
        find_duplicates(
            candidate,
            corpus,
            embedder=embedder,
            near_hash_threshold=near_hash_threshold,
            semantic_threshold=semantic_threshold,
        )
    )


@dataclass
class DedupIndex:
    """Incremental, in-memory dedup index.

    ``add`` returns any verdicts against already-indexed items but only stores
    the new item when it is unique, keeping the canonical set free of
    duplicates. Removing an existing canonical item is consequential and is not
    handled here (permission ladder).
    """

    embedder: Optional[Embedder] = None
    near_hash_threshold: float = DEFAULT_NEAR_HASH_THRESHOLD
    semantic_threshold: float = DEFAULT_SEMANTIC_THRESHOLD
    _items: List[ContentItem] = field(default_factory=list)
    _hashes: Dict[str, str] = field(default_factory=dict)  # hash -> content_id

    @property
    def items(self) -> List[ContentItem]:
        return list(self._items)

    def add(self, item: ContentItem) -> List[DuplicateVerdict]:
        verdicts = find_duplicates(
            item,
            self._items,
            embedder=self.embedder,
            near_hash_threshold=self.near_hash_threshold,
            semantic_threshold=self.semantic_threshold,
        )
        if not verdicts:
            self._items.append(item)
            self._hashes[item.hash] = item.content_id
        return verdicts
