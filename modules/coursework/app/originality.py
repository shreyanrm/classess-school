"""Originality / similarity check interface (B6).

Checks whether a submitted response is the learner's own work. This is an
INTERFACE with a working deterministic fallback, not a verdict engine:

  - it NEVER auto-accuses. Originality is a SIGNAL routed to a human, on the
    permission ladder at RECOMMEND — a teacher reviews, a teacher decides.
  - with no external similarity provider configured, it runs a deterministic
    in-process near-duplicate check (token-shingle Jaccard) against a supplied
    corpus, and clearly labels itself as the degraded local check.
  - a high-similarity result raises a REVIEW flag (needs_human_review), never a
    penalty and never a mark change.

No I/O. The provider seam (``SimilarityProvider``) is where an external service
plugs in; its key name is ``clss.coursework.dev.originality_provider_key``
(read by NAME, never hardcoded).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol
from uuid import UUID


class OriginalitySignal(str, Enum):
    """The signal band — a recommendation to a human, never a judgment."""

    LIKELY_ORIGINAL = "likely_original"
    NEEDS_REVIEW = "needs_review"  # high similarity OR provider abstained on a stakes item
    UNDETERMINED = "undetermined"  # no corpus / no provider — cannot assess


@dataclass(frozen=True)
class SimilarityMatch:
    """One matched source and its similarity score in [0,1]."""

    source_ref: str  # opaque ref to the matched source (another submission id, a doc id) — never PII
    score: float
    snippet: str | None = None


@dataclass(frozen=True)
class OriginalityResult:
    """The originality assessment. A SIGNAL on the RECOMMEND rung — it flags for
    human review; it never changes a mark and never accuses automatically."""

    submission_ref: UUID
    signal: OriginalitySignal
    max_similarity: float
    matches: list[SimilarityMatch] = field(default_factory=list)
    needs_human_review: bool = False
    provider: str = "deterministic-local (degraded — set clss.coursework.dev.originality_provider_key)"
    rationale: str = ""

    @property
    def rung(self) -> str:
        """Permission-ladder rung: always RECOMMEND — a human owns the decision."""
        return "recommend"


class SimilarityProvider(Protocol):
    """An external similarity service. Returns matches against a corpus.

    With no live provider, use ``DeterministicLocalSimilarity`` — it runs a real
    in-process shingle check and labels itself as the degraded path.
    """

    def compare(self, *, text: str, corpus: dict[str, str]) -> list[SimilarityMatch]:
        ...


def _shingles(text: str, k: int = 3) -> set[str]:
    """k-word shingles, normalized — the unit of near-duplicate comparison."""
    tokens = re.findall(r"\w+", text.lower())
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass(frozen=True)
class DeterministicLocalSimilarity:
    """No-provider default: a token-shingle Jaccard near-duplicate check. Real,
    in-process, no external call. Clearly the degraded path."""

    k: int = 3

    def compare(self, *, text: str, corpus: dict[str, str]) -> list[SimilarityMatch]:
        target = _shingles(text, self.k)
        matches: list[SimilarityMatch] = []
        for source_ref, source_text in corpus.items():
            score = _jaccard(target, _shingles(source_text, self.k))
            if score > 0.0:
                matches.append(SimilarityMatch(source_ref=source_ref, score=score))
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches


# A similarity at/above this raises a review flag. A SIGNAL threshold, not a
# guilt threshold — the human decides what it means.
REVIEW_SIMILARITY_THRESHOLD = 0.65


def check_originality(
    *,
    submission_ref: UUID,
    text: str,
    corpus: dict[str, str] | None = None,
    provider: SimilarityProvider | None = None,
    review_threshold: float = REVIEW_SIMILARITY_THRESHOLD,
) -> OriginalityResult:
    """Assess originality of ``text`` against ``corpus``.

    ``provider`` plugs in an external service; absent one, the deterministic
    local check runs. ``corpus`` maps an opaque source ref -> source text. With
    no corpus and no provider the result is UNDETERMINED (cannot assess), never a
    false clearance.
    """
    if corpus is None and provider is None:
        return OriginalityResult(
            submission_ref=submission_ref,
            signal=OriginalitySignal.UNDETERMINED,
            max_similarity=0.0,
            needs_human_review=False,
            rationale="No corpus and no similarity provider — originality could not be assessed.",
        )

    used = provider if provider is not None else DeterministicLocalSimilarity()
    provider_label = (
        "external similarity provider"
        if provider is not None
        else "deterministic-local (degraded — set clss.coursework.dev.originality_provider_key)"
    )
    matches = used.compare(text=text, corpus=corpus or {})
    max_sim = max((m.score for m in matches), default=0.0)

    if max_sim >= review_threshold:
        signal = OriginalitySignal.NEEDS_REVIEW
        needs_review = True
        rationale = (
            f"Highest similarity {max_sim:.2f} meets the review threshold {review_threshold:.2f}. "
            "Flagged for a teacher to review — this is a signal, not a finding, and changes no mark."
        )
    else:
        signal = OriginalitySignal.LIKELY_ORIGINAL
        needs_review = False
        rationale = f"Highest similarity {max_sim:.2f} is below the review threshold {review_threshold:.2f}."

    return OriginalityResult(
        submission_ref=submission_ref,
        signal=signal,
        max_similarity=max_sim,
        matches=matches[:10],
        needs_human_review=needs_review,
        provider=provider_label,
        rationale=rationale,
    )
