"""A simple RETRIEVAL hook for grounding generation (A4).

The fabric grounds generation in retrieved context (curriculum nodes, prior
verified items, ontology snippets) before it calls a provider. This module is
the SEAM, not a vector store: a :class:`Retriever` returns a list of
:class:`RetrievedContext` snippets for a query; the orchestrator folds them into
the provider prompt and records how many were used on the trace span.

Defaults degrade gracefully:
  - :class:`NullRetriever` returns nothing — generation proceeds ungrounded
    (the fabric runs with no retrieval backend wired),
  - :class:`StaticRetriever` returns a fixed corpus filtered by token overlap —
    a real, dependency-free retriever for tests and local grounding.

No PII is retrieved or stored here: snippets are curriculum / content text keyed
by an opaque ``source_id``. No secret is ever read in this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RetrievedContext:
    """One grounding snippet. ``source_id`` is opaque (no PII)."""

    source_id: str
    text: str
    score: float = 0.0


class Retriever(Protocol):
    """The retrieval seam. Returns the top-k grounding snippets for a query."""

    def retrieve(self, *, query: str, task_class: str, k: int = 3) -> list[RetrievedContext]:
        ...


@dataclass
class NullRetriever:
    """The no-backend default: retrieves nothing (ungrounded generation)."""

    def retrieve(self, *, query: str, task_class: str, k: int = 3) -> list[RetrievedContext]:
        return []


_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


@dataclass
class StaticRetriever:
    """A real, dependency-free retriever over an in-memory corpus.

    Scores each snippet by token overlap with the query (a simple lexical match
    — no embeddings, no network) and returns the top-k by score. Empty or
    no-overlap queries return nothing, so generation stays ungrounded rather than
    grounded on noise.
    """

    corpus: list[RetrievedContext] = field(default_factory=list)

    def retrieve(self, *, query: str, task_class: str, k: int = 3) -> list[RetrievedContext]:
        q = _tokens(query)
        if not q or k <= 0:
            return []
        scored: list[RetrievedContext] = []
        for snippet in self.corpus:
            overlap = q & _tokens(snippet.text)
            if not overlap:
                continue
            score = len(overlap) / len(q)
            scored.append(RetrievedContext(source_id=snippet.source_id, text=snippet.text, score=score))
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:k]
