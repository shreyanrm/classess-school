"""Blueprint coverage view for the paper author (B6, domain 10).

The dossier: the author works against "a colour-coded view of completed,
untaught, and previously examined topics". This module computes that view —
given the topics a blueprint intends to assess, and the curriculum state the
author is drawing on, it classifies every topic into one of four statuses and
explains the mix, so the author sees at a glance whether they are testing what
was taught and not over-testing what was already examined.

The four statuses (the dossier's three + an explicit completed-and-already-tested
overlap surfaced for the author):

  - COMPLETED            — taught and ready to assess, not examined before,
  - UNTAUGHT             — NOT yet taught (a warning: testing the untaught),
  - PREVIOUSLY_EXAMINED  — taught AND already examined before (over-test risk),
  - NOT_IN_BLUEPRINT     — taught/available but the blueprint does not cover it
                           (a coverage gap the author may want to close).

This is a VIEW, not a gate. It never blocks a paper — it informs the author, who
decides. Topic refs are opaque ``UUID`` ids (board-agnostic, never PII); the
curriculum status is CONSUMED from the ontology/curriculum layer, never computed
or owned here (altitude: a School module never owns a spine concern).

Pure: no I/O, no network. Import-safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID

from .papers import Blueprint


class TopicCoverageStatus(str, Enum):
    """The colour-coded status of one topic in the coverage view."""

    COMPLETED = "completed"  # taught, not previously examined — ready to assess
    UNTAUGHT = "untaught"  # not yet taught — testing it is a warning
    PREVIOUSLY_EXAMINED = "previously_examined"  # taught and already examined — over-test risk
    NOT_IN_BLUEPRINT = "not_in_blueprint"  # taught/available but this blueprint omits it


# A suggested colour token per status (board-agnostic UI hint; not a hard style).
STATUS_COLOUR: dict[TopicCoverageStatus, str] = {
    TopicCoverageStatus.COMPLETED: "green",
    TopicCoverageStatus.UNTAUGHT: "amber",
    TopicCoverageStatus.PREVIOUSLY_EXAMINED: "blue",
    TopicCoverageStatus.NOT_IN_BLUEPRINT: "grey",
}


@dataclass(frozen=True)
class TopicCoverage:
    """One topic's place in the coverage view: its status, a colour hint, and a
    plain-language reason — explainable for the author."""

    topic_id: UUID
    status: TopicCoverageStatus
    colour: str
    rationale: str


@dataclass(frozen=True)
class CoverageView:
    """The full coverage view over a blueprint: every relevant topic classified,
    a per-status roll-up, and a plain-language summary. A VIEW for the author to
    act on — it never blocks the paper."""

    blueprint_id: UUID
    topics: list[TopicCoverage] = field(default_factory=list)
    summary: str = ""

    def of_status(self, status: TopicCoverageStatus) -> list[UUID]:
        return [t.topic_id for t in self.topics if t.status is status]

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {s.value: 0 for s in TopicCoverageStatus}
        for t in self.topics:
            out[t.status.value] += 1
        return out

    @property
    def testing_untaught(self) -> bool:
        """True when the blueprint assesses one or more not-yet-taught topics — the
        author's headline warning."""
        return any(t.status is TopicCoverageStatus.UNTAUGHT for t in self.topics)


def _blueprint_topic_ids(blueprint: Blueprint) -> set[UUID]:
    return {c.ontology.topic_id for c in blueprint.cells}


def compute_coverage(
    blueprint: Blueprint,
    *,
    taught_topic_ids: set[UUID],
    previously_examined_topic_ids: set[UUID] | None = None,
    curriculum_topic_ids: set[UUID] | None = None,
) -> CoverageView:
    """Compute the coverage view for ``blueprint``.

    ``taught_topic_ids`` are the topics the author has completed teaching;
    ``previously_examined_topic_ids`` are topics already examined in a prior
    paper; ``curriculum_topic_ids`` (optional) is the wider available curriculum
    used to surface NOT_IN_BLUEPRINT gaps. All are opaque ids drawn from the
    curriculum layer — this module classifies, it never owns the curriculum.

    Classification, per topic the blueprint covers:
      - in ``previously_examined`` -> PREVIOUSLY_EXAMINED (taught & already tested),
      - else in ``taught``         -> COMPLETED (ready to assess),
      - else                       -> UNTAUGHT (a warning).
    Topics in the curriculum the blueprint does NOT cover are NOT_IN_BLUEPRINT.
    """
    previously_examined_topic_ids = previously_examined_topic_ids or set()
    in_blueprint = _blueprint_topic_ids(blueprint)

    topics: list[TopicCoverage] = []
    for topic_id in sorted(in_blueprint, key=str):
        if topic_id in previously_examined_topic_ids:
            status = TopicCoverageStatus.PREVIOUSLY_EXAMINED
            reason = "Taught and already examined in a prior paper — re-testing it risks over-assessing."
        elif topic_id in taught_topic_ids:
            status = TopicCoverageStatus.COMPLETED
            reason = "Taught and not examined before — ready to assess."
        else:
            status = TopicCoverageStatus.UNTAUGHT
            reason = "Not yet taught — assessing it now tests material the class has not covered."
        topics.append(
            TopicCoverage(topic_id=topic_id, status=status, colour=STATUS_COLOUR[status], rationale=reason)
        )

    # Coverage gaps: curriculum topics the blueprint omits.
    if curriculum_topic_ids:
        for topic_id in sorted(curriculum_topic_ids - in_blueprint, key=str):
            topics.append(
                TopicCoverage(
                    topic_id=topic_id,
                    status=TopicCoverageStatus.NOT_IN_BLUEPRINT,
                    colour=STATUS_COLOUR[TopicCoverageStatus.NOT_IN_BLUEPRINT],
                    rationale="In the curriculum but not covered by this blueprint — a coverage gap to consider.",
                )
            )

    counts = {s.value: sum(1 for t in topics if t.status is s) for s in TopicCoverageStatus}
    parts = [
        f"{counts['completed']} completed",
        f"{counts['untaught']} untaught",
        f"{counts['previously_examined']} previously examined",
    ]
    if counts["not_in_blueprint"]:
        parts.append(f"{counts['not_in_blueprint']} not in this blueprint")
    summary = (
        "Coverage view: " + ", ".join(parts) + ". "
        + (
            "WARNING: this paper assesses topics that have not yet been taught. "
            if any(t.status is TopicCoverageStatus.UNTAUGHT for t in topics)
            else ""
        )
        + "This is a view for the author — it never blocks the paper."
    )
    return CoverageView(blueprint_id=blueprint.blueprint_id, topics=topics, summary=summary)
