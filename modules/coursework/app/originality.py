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


# ---------------------------------------------------------------------------
# Comparison SOURCES — the dossier's "against the web, against classmates, and
# against model answers". Each is a labelled corpus the same check runs over.
# ---------------------------------------------------------------------------
class ComparisonSource(str, Enum):
    """Where a similarity match came from — surfaced so a human sees the context.

      - PEER         — another classmate's submission,
      - MODEL_ANSWER — a teacher/board model answer,
      - WEB          — an external web source (via a provider seam).
    """

    PEER = "peer"
    MODEL_ANSWER = "model_answer"
    WEB = "web"


@dataclass(frozen=True)
class SourcedOriginalityResult:
    """An originality read that keeps WHICH kind of source each top match came
    from, so the human review shows web vs peer vs model-answer overlap. Still a
    RECOMMEND-rung signal — it never accuses and never changes a mark."""

    base: OriginalityResult
    by_source: dict[ComparisonSource, float]  # source kind -> max similarity from that kind

    @property
    def signal(self) -> OriginalitySignal:
        return self.base.signal

    @property
    def needs_human_review(self) -> bool:
        return self.base.needs_human_review

    @property
    def rung(self) -> str:
        return "recommend"


def check_originality_sourced(
    *,
    submission_ref: UUID,
    text: str,
    peer_corpus: dict[str, str] | None = None,
    model_answers: dict[str, str] | None = None,
    web_corpus: dict[str, str] | None = None,
    provider: SimilarityProvider | None = None,
    review_threshold: float = REVIEW_SIMILARITY_THRESHOLD,
) -> SourcedOriginalityResult:
    """Compare ``text`` against the three labelled source kinds at once — peers,
    model answers, and the web — and keep which kind drove the top similarity.

    Each corpus is namespaced so a match's source kind is recoverable; the
    underlying check is the same deterministic-or-provider path as
    ``check_originality``. With nothing to compare against the base result is
    UNDETERMINED. Never accuses; routes a high overlap to a human."""
    combined: dict[str, str] = {}
    source_of: dict[str, ComparisonSource] = {}
    for kind, corpus in (
        (ComparisonSource.PEER, peer_corpus),
        (ComparisonSource.MODEL_ANSWER, model_answers),
        (ComparisonSource.WEB, web_corpus),
    ):
        for ref, src_text in (corpus or {}).items():
            key = f"{kind.value}:{ref}"
            combined[key] = src_text
            source_of[key] = kind

    base = check_originality(
        submission_ref=submission_ref,
        text=text,
        corpus=combined or None,
        provider=provider,
        review_threshold=review_threshold,
    )
    by_source: dict[ComparisonSource, float] = {}
    for m in base.matches:
        kind = source_of.get(m.source_ref)
        if kind is None:
            continue
        by_source[kind] = max(by_source.get(kind, 0.0), m.score)
    return SourcedOriginalityResult(base=base, by_source=by_source)


# ---------------------------------------------------------------------------
# Style-shift detection — a sudden change in writing style is a SIGNAL, not a
# verdict. Deterministic, in-process: compares simple, board-agnostic style
# features of this submission against the learner's own past work. A large shift
# raises a review flag and (downstream) the ask-to-explain interaction.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StyleProfile:
    """A small bag of deterministic, language-agnostic style features in [0,1]-ish
    space. Computed from text only; carries no content and no PII."""

    avg_word_length: float
    avg_sentence_length: float
    type_token_ratio: float  # vocabulary richness: distinct words / total words

    @staticmethod
    def from_text(text: str) -> "StyleProfile":
        words = re.findall(r"\w+", text.lower())
        sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
        n_words = len(words) or 1
        n_sent = len(sentences) or 1
        avg_wl = sum(len(w) for w in words) / n_words
        avg_sl = n_words / n_sent
        ttr = len(set(words)) / n_words
        return StyleProfile(avg_word_length=avg_wl, avg_sentence_length=avg_sl, type_token_ratio=ttr)

    def distance(self, other: "StyleProfile") -> float:
        """A normalized [0,1] style distance from another profile. Larger means a
        bigger style shift. Each feature is normalized by a reasonable scale so no
        single feature dominates."""
        wl = abs(self.avg_word_length - other.avg_word_length) / 6.0
        sl = abs(self.avg_sentence_length - other.avg_sentence_length) / 25.0
        tt = abs(self.type_token_ratio - other.type_token_ratio)
        return max(0.0, min(1.0, (wl + sl + tt) / 3.0))


# A style distance at/above this raises a style-shift review flag. A SIGNAL
# threshold (a human decides), never a guilt threshold.
STYLE_SHIFT_THRESHOLD = 0.5


@dataclass(frozen=True)
class StyleShiftResult:
    """A style-shift read: the distance from the learner's baseline and whether it
    crosses the review threshold. A RECOMMEND-rung signal — never an accusation."""

    submission_ref: UUID
    distance: float
    shifted: bool
    needs_human_review: bool
    rationale: str

    @property
    def rung(self) -> str:
        return "recommend"


def detect_style_shift(
    *,
    submission_ref: UUID,
    text: str,
    baseline_texts: list[str],
    threshold: float = STYLE_SHIFT_THRESHOLD,
) -> StyleShiftResult:
    """Compare this submission's style to the learner's OWN past work.

    With no baseline the result cannot assess a shift (distance 0, no flag — never
    a false positive). A large distance raises a review flag and a plain-language
    reason for the teacher. This NEVER changes a mark and NEVER accuses; it asks a
    human to look, optionally inviting the explain-or-rewrite interaction."""
    baseline_texts = [t for t in baseline_texts if t and t.strip()]
    if not baseline_texts:
        return StyleShiftResult(
            submission_ref=submission_ref,
            distance=0.0,
            shifted=False,
            needs_human_review=False,
            rationale="No prior work on file — a style shift cannot be assessed.",
        )
    this = StyleProfile.from_text(text)
    baseline = [StyleProfile.from_text(t) for t in baseline_texts]
    # Compare against the mean baseline profile.
    mean = StyleProfile(
        avg_word_length=sum(b.avg_word_length for b in baseline) / len(baseline),
        avg_sentence_length=sum(b.avg_sentence_length for b in baseline) / len(baseline),
        type_token_ratio=sum(b.type_token_ratio for b in baseline) / len(baseline),
    )
    dist = this.distance(mean)
    shifted = dist >= threshold
    if shifted:
        rationale = (
            f"Writing style differs from this learner's past work (shift {dist:.2f} "
            f">= {threshold:.2f}). Flagged for a teacher to look — a signal, not a finding; "
            "no mark changes. Consider asking the learner to explain or rewrite in their own words."
        )
    else:
        rationale = f"Writing style is consistent with past work (shift {dist:.2f} < {threshold:.2f})."
    return StyleShiftResult(
        submission_ref=submission_ref,
        distance=dist,
        shifted=shifted,
        needs_human_review=shifted,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Ask-to-explain-or-rewrite — the dossier's care-ful interaction. When a concern
# is raised, the learner is INVITED (never compelled, never accused) to explain
# their work or rewrite it in their own words. This produces a prompt + a record
# of the invitation; the teacher still judges. It is NOT a punishment.
# ---------------------------------------------------------------------------
class ExplainOrRewriteAction(str, Enum):
    EXPLAIN = "explain"  # explain the work / reasoning in their own words
    REWRITE = "rewrite"  # rewrite the passage in their own words


@dataclass(frozen=True)
class ExplainOrRewriteRequest:
    """An invitation to a learner to explain or rewrite, raised off an originality
    or style-shift concern. A care-ful interaction: it states the concern
    neutrally, invites a response, and makes clear no judgement has been made and
    no mark has changed. The teacher reviews the response and decides."""

    submission_ref: UUID
    action: ExplainOrRewriteAction
    prompt: str
    triggered_by: str  # neutral label of what raised it (e.g. 'similarity', 'style_shift')

    @property
    def rung(self) -> str:
        """RECOMMEND — an invitation a human oversees; never an automatic penalty."""
        return "recommend"


def ask_to_explain_or_rewrite(
    *,
    submission_ref: UUID,
    action: ExplainOrRewriteAction = ExplainOrRewriteAction.EXPLAIN,
    triggered_by: str = "originality_signal",
) -> ExplainOrRewriteRequest:
    """Build a neutral, care-ful invitation for the learner to explain or rewrite.

    The wording never accuses and never asserts wrongdoing — it asks the learner
    to show their understanding. Used after an originality or style-shift concern;
    the teacher still owns the outcome."""
    if action is ExplainOrRewriteAction.EXPLAIN:
        prompt = (
            "We'd like to understand your thinking on this answer. In your own words, "
            "can you explain how you worked it out and what it means? There's no penalty — "
            "this just helps your teacher see your understanding."
        )
    else:
        prompt = (
            "Could you rewrite this answer in your own words? It helps your teacher see your "
            "understanding clearly. There's no penalty for being asked — take your time."
        )
    return ExplainOrRewriteRequest(
        submission_ref=submission_ref,
        action=action,
        prompt=prompt,
        triggered_by=triggered_by,
    )
