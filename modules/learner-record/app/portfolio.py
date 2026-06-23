"""The portfolio (B8) — curated artifacts with provenance.

A portfolio is a learner-curated collection of artifacts (a project, a piece of
writing, a solved problem set) that demonstrate what the learner can do. Each
artifact carries:

  - PROVENANCE: the opaque source event-ids and the ontology topic it evidences,
    plus the independent-vs-supported mode it was produced under. An artifact
    with no provenance cannot be added — evidence over assertion (principle 7).
  - PERMISSION CONTROLS: it is curated and shared only under the learner's
    control, behind the consent + purpose gate.

Reads of a portfolio pass the gate (scope ``portfolio``). Curation (add/feature)
is the learner acting on their OWN record — still gated to the learner's own
consent so the audit trail is complete, and emitted as append-only events.

PII-FREE: opaque ids only; an artifact stores a reference and a plain-language
title/caption, never a name, email, or raw score.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Literal

from .access import ConsentGrant, ReadRequest, require

# How an artifact was produced — the keystone flag carried through to the
# portfolio so a "look what I made" item is honest about whether it was done
# alone or with help (mirrors attempt.ts AttemptMode).
ProducedMode = Literal["independent", "supported"]

# Numbers/percentages/formula must not appear in a learner-facing caption.
_FORBIDDEN_IN_CAPTION = re.compile(r"%|=|\^|product of")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class ArtifactProvenance:
    """Where an artifact came from. Opaque references only."""

    topic_id: str
    source_event_ids: tuple[str, ...]
    produced_mode: ProducedMode
    produced_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.source_event_ids:
            raise ValueError(
                "An artifact must carry provenance — at least one source event "
                "id. No artifact without evidence."
            )


@dataclass(frozen=True)
class Artifact:
    """One curated portfolio artifact.

    ``caption`` is learner-facing and must stay plain — no raw score lives here
    (a portfolio shows the work, not a number). ``content_ref`` is an opaque
    handle into governed storage, never an inline blob and never PII.
    """

    artifact_id: str
    subject: str                        # opaque canonical_uuid (the owner)
    title: str
    content_ref: str                    # opaque handle into governed storage
    provenance: ArtifactProvenance
    caption: str = ""
    featured: bool = False
    added_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.caption and _FORBIDDEN_IN_CAPTION.search(self.caption):
            raise ValueError(
                "A portfolio caption must not contain a percentage or formula "
                "(a portfolio shows the work, not a score)."
            )


class Portfolio:
    """A learner's append-only curated collection.

    Curation is additive: artifacts are appended and features toggled by
    emitting new state, never by mutating evidence. The collection is owned by
    the opaque subject; assembling a SHARED view of it passes the consent +
    purpose gate.
    """

    def __init__(self, subject: str) -> None:
        self._subject = subject
        self._artifacts: list[Artifact] = []

    @property
    def subject(self) -> str:
        return self._subject

    def add(
        self,
        *,
        title: str,
        content_ref: str,
        provenance: ArtifactProvenance,
        caption: str = "",
        featured: bool = False,
        artifact_id: str | None = None,
        added_at: datetime | None = None,
    ) -> Artifact:
        """Curate an artifact into the portfolio. Requires provenance (enforced
        by ``ArtifactProvenance``). Returns the stored artifact."""
        artifact = Artifact(
            artifact_id=artifact_id or _new_id(),
            subject=self._subject,
            title=title,
            content_ref=content_ref,
            provenance=provenance,
            caption=caption,
            featured=featured,
            added_at=added_at or _now(),
        )
        self._artifacts.append(artifact)
        return artifact

    def all(self) -> tuple[Artifact, ...]:
        """The owner's full view of their own collection (un-shared)."""
        return tuple(self._artifacts)

    def featured(self) -> tuple[Artifact, ...]:
        return tuple(a for a in self._artifacts if a.featured)

    def shared_view(
        self,
        *,
        request: ReadRequest,
        grants: Iterable[ConsentGrant],
        asof: datetime | None = None,
        featured_only: bool = False,
    ) -> tuple[Artifact, ...]:
        """A consent + purpose-gated view of the portfolio for a viewer.

        GATED FIRST (denied-by-default): the consent check runs before any
        artifact is returned. Scope must be ``portfolio``. A read without a
        satisfied consent check raises ``ConsentDenied`` and nothing is
        returned.
        """
        require(request, grants, asof=asof)
        items = self.featured() if featured_only else self.all()
        return items


__all__ = [
    "ProducedMode",
    "ArtifactProvenance",
    "Artifact",
    "Portfolio",
]
