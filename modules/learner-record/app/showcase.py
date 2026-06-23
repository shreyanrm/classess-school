"""Year-end portfolio compilation + the student-owned SHOWCASE (B8).

The doc (section 14): "A year-end portfolio, a student-owned showcase, and
verifiable credentials." Two distinct things live here:

  - The YEAR-END PORTFOLIO COMPILATION — a point-in-time, immutable snapshot of
    a learner's portfolio assembled at the close of a period. It is a curated,
    provenance-carrying record of the year's work; once compiled it does not
    change (append-only spirit — a new year is a new compilation).
  - The student-owned SHOWCASE — a DISTINCT view the LEARNER controls and
    presents. Where the gated ``Portfolio.shared_view`` answers "what may this
    viewer see", the showcase answers "what does the LEARNER choose to show".
    It is the learner's own stage: featured artifacts, in the learner's order,
    with a plain-language headline they author.

Hard rules: PII-FREE (opaque ids only); PLAIN LANGUAGE (no number/percentage/
formula in the headline or captions); EVIDENCE-LINKED (every showcased item is
a portfolio artifact, which already requires provenance); GATED when SHARED with
anyone other than the holder (consent + purpose, scope ``portfolio``). A learner
viewing their OWN showcase is in-audience by construction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .access import ConsentGrant, ReadRequest, require
from .portfolio import Artifact, Portfolio

# A headline is learner-facing — no percentage/formula (a showcase shows the
# work, not a score). Mirrors the caption guard in portfolio.py.
_FORBIDDEN_IN_HEADLINE = re.compile(r"%|=|\^|product of")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class YearEndPortfolio:
    """An immutable year-end compilation of a learner's portfolio.

    A point-in-time snapshot: the artifacts as they stood at ``compiled_at`` for
    the named ``period``. PII-free; every artifact already carries provenance.
    """

    subject: str                       # opaque canonical_uuid
    period: str                        # opaque period label, e.g. "year-2025-26"
    artifacts: tuple[Artifact, ...]
    compiled_at: datetime

    @property
    def featured(self) -> tuple[Artifact, ...]:
        return tuple(a for a in self.artifacts if a.featured)

    @property
    def topic_ids(self) -> tuple[str, ...]:
        """The distinct topics the year's work evidences (opaque ids, ordered)."""
        seen: list[str] = []
        for a in self.artifacts:
            tid = a.provenance.topic_id
            if tid not in seen:
                seen.append(tid)
        return tuple(seen)


def compile_year_end(
    portfolio: Portfolio,
    *,
    period: str,
    compiled_at: datetime | None = None,
) -> YearEndPortfolio:
    """Compile an immutable year-end snapshot of a learner's portfolio.

    This is the owner compiling their OWN record, so it is not a cross-context
    read; the snapshot is taken from the owner's full collection. Sharing the
    compilation with a viewer still passes the gate (use ``Portfolio`` /
    ``Showcase`` gated views for that). Returns a frozen snapshot.
    """
    return YearEndPortfolio(
        subject=portfolio.subject,
        period=period,
        artifacts=portfolio.all(),
        compiled_at=compiled_at or _now(),
    )


@dataclass(frozen=True)
class Showcase:
    """The student-owned showcase — what the LEARNER chooses to present.

    Distinct from the gated portfolio read: this is the learner's stage. They
    author the ``headline`` and choose the ``items`` (a curated, ordered subset
    of their own artifacts). All artifacts must belong to the subject and carry
    provenance (enforced upstream by ``Portfolio``).
    """

    subject: str                       # opaque canonical_uuid (the owner)
    headline: str                      # learner-authored, plain language, no score
    items: tuple[Artifact, ...]
    curated_at: datetime

    def __post_init__(self) -> None:
        if self.headline and _FORBIDDEN_IN_HEADLINE.search(self.headline):
            raise ValueError(
                "A showcase headline must not contain a percentage or formula "
                "(a showcase shows the work, not a score)."
            )
        for art in self.items:
            if art.subject != self.subject:
                raise ValueError(
                    "A showcase may only present the owner's own artifacts."
                )


def build_showcase(
    portfolio: Portfolio,
    *,
    headline: str = "",
    artifact_ids: Iterable[str] | None = None,
    curated_at: datetime | None = None,
) -> Showcase:
    """Build the learner's own showcase from their portfolio.

    The learner chooses the order via ``artifact_ids``; when omitted the
    featured artifacts (in curation order) form the showcase — the learner's
    "look what I made" default. This composes from the OWNER's own collection
    (self-curation); SHARING it is gated via :func:`shared_showcase`.
    """
    by_id = {a.artifact_id: a for a in portfolio.all()}
    if artifact_ids is None:
        items = portfolio.featured()
    else:
        items = tuple(by_id[aid] for aid in artifact_ids)
    return Showcase(
        subject=portfolio.subject,
        headline=headline,
        items=items,
        curated_at=curated_at or _now(),
    )


def shared_showcase(
    showcase: Showcase,
    *,
    request: ReadRequest,
    grants: Iterable[ConsentGrant],
    asof: datetime | None = None,
) -> Showcase:
    """A consent + purpose-gated read of a learner's showcase for a viewer.

    GATED FIRST (denied-by-default). Scope must be ``portfolio``. The learner
    viewing their own showcase is in-audience by construction; any other viewer
    needs a satisfying grant. Returns the showcase unchanged on ALLOW; raises
    ``ConsentDenied`` otherwise.
    """
    require(request, grants, asof=asof)
    return showcase


__all__ = [
    "YearEndPortfolio",
    "compile_year_end",
    "Showcase",
    "build_showcase",
    "shared_showcase",
]
