"""The continuous academic timeline (B8) — one ordered, evidence-linked story.

The doc (section 14) asks for a CONTINUOUS academic timeline: "concept and skill
mastery, projects, achievements, teacher observations, and reflections — every
conclusion linked to its evidence." This module composes governed signals into a
single chronological record the School (and, gated, the learner/parent) can read.

Hard rules honoured here (the same twelve invariants the rest of B8 obeys):

  - PLAIN LANGUAGE ONLY. Every learner/parent-facing summary passes
    :func:`profile.assert_plain_language` — no number, percentage, or formula
    ever lands on a timeline entry (the mastery scalar is a spine concern).
  - EVERY ENTRY LINKS TO EVIDENCE. No timeline entry exists without its source
    event-id lineage (principle 7: evidence over assertion). The constructor
    refuses an entry with no source events.
  - GATED. The timeline is assembled only behind the consent + purpose gate
    (``access.require``); scope ``mastery-profile``. A read without a satisfied
    consent check raises ``ConsentDenied`` and nothing is returned.
  - PII-FREE. Keyed by the opaque ``canonical_uuid``; entries carry opaque
    topic/source ids and plain-language text only — never a name, email, or
    raw score.

B8 does NOT author these signals. Mastery, project outcomes, observations and
reflections are evidence captured elsewhere (CORE/spine) and READ here through
governed views; this module orders, shapes, gates and explains them. It never
recomputes a judgment and never invents an entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable

from .access import ConsentGrant, ReadRequest, require
from .profile import PermissionControls, assert_plain_language


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimelineKind(str, Enum):
    """The item kinds the doc enumerates for the continuous timeline.

    Each is a distinct, evidence-linked moment in the learner's story. They are
    rendered together, oldest-to-newest, as one continuous record.
    """

    MASTERY = "mastery"            # a concept/skill became independent (or shifted band)
    PROJECT = "project"           # a project milestone or completion
    ACHIEVEMENT = "achievement"   # a recognised achievement (badge/certificate moment)
    OBSERVATION = "observation"   # a teacher's recorded observation
    REFLECTION = "reflection"     # the learner's own reflection / self-assessment


# Who authored a reflection vs an observation matters for honesty: a reflection
# is the LEARNER's own voice; an observation is a TEACHER's recorded note. We
# track the author ROLE (opaque, coarse) — never the person.
AuthorRole = tuple[str, ...]  # informational alias; concrete values below
AUTHOR_LEARNER = "learner"
AUTHOR_TEACHER = "teacher"
AUTHOR_SYSTEM = "system"  # an evidence-derived entry (e.g. mastery shift)


@dataclass(frozen=True)
class TimelineEntry:
    """One evidence-linked moment on the continuous academic timeline.

    There is NO mastery number on this object by design; ``summary`` is the
    plain-language sentence a surface renders, and it is guarded on construction.
    """

    entry_id: str
    subject: str                       # opaque canonical_uuid (the learner)
    kind: TimelineKind
    occurred_at: datetime
    summary: str                       # learner-safe plain language, no number
    source_event_ids: tuple[str, ...]
    permissions: PermissionControls
    topic_id: str | None = None        # opaque ontology id when topic-bound
    author_role: str = AUTHOR_SYSTEM   # learner / teacher / system

    def __post_init__(self) -> None:
        assert_plain_language(self.summary)
        if not self.source_event_ids:
            raise ValueError(
                "A timeline entry must link to at least one source event — no "
                "entry exists without evidence (evidence over assertion)."
            )


@dataclass(frozen=True)
class TimelineSignal:
    """The INPUT shape — a governed signal as it arrives from a gated read view.

    It carries the already-derived plain-language summary plus its lineage and
    kind; it NEVER carries the composite mastery number (the governed view omits
    it for display consumers). The timeline composes these into ``TimelineEntry``
    objects; it never recomputes a judgment.
    """

    kind: TimelineKind
    occurred_at: datetime
    summary: str
    source_event_ids: tuple[str, ...]
    topic_id: str | None = None
    author_role: str = AUTHOR_SYSTEM
    entry_id: str | None = None


def _why_visible(viewer_self: bool, scope: str) -> str:
    if viewer_self:
        return "This is your own timeline."
    return f"The learner consented to share their {scope.replace('-', ' ')} with you."


@dataclass(frozen=True)
class LearnerTimeline:
    """The composed, gated, plain-language continuous timeline for one learner."""

    subject: str
    entries: tuple[TimelineEntry, ...]
    composed_at: datetime
    degraded_reasons: tuple[str, ...] = ()

    def of_kind(self, kind: TimelineKind) -> tuple[TimelineEntry, ...]:
        return tuple(e for e in self.entries if e.kind == kind)

    @property
    def observations(self) -> tuple[TimelineEntry, ...]:
        return self.of_kind(TimelineKind.OBSERVATION)

    @property
    def reflections(self) -> tuple[TimelineEntry, ...]:
        return self.of_kind(TimelineKind.REFLECTION)

    def since(self, when: datetime) -> tuple[TimelineEntry, ...]:
        """Entries on/after ``when`` — the "what changed lately" read."""
        return tuple(e for e in self.entries if e.occurred_at >= when)


def compose_timeline(
    signals: Iterable[TimelineSignal],
    *,
    request: ReadRequest,
    grants: Iterable[ConsentGrant],
    asof: datetime | None = None,
    degraded_reasons: Iterable[str] | None = None,
) -> LearnerTimeline:
    """Compose the continuous academic timeline from governed signals.

    GATED FIRST (denied-by-default): the consent + purpose check runs before any
    signal is read. Scope must be ``mastery-profile``. A read without a satisfied
    consent check raises ``ConsentDenied`` and no timeline is built.

    Entries are ordered oldest-to-newest so a surface renders one continuous
    story. Every entry carries its source lineage and the permission controls
    derived from the satisfying grant; no number ever lands on the output.
    """
    asof = asof or _now()
    grants = list(grants)

    access = require(request, grants, asof=asof)
    satisfying = next(g for g in grants if g.consent_id == access.consent_id)
    viewer_self = request.viewer == request.subject
    why = _why_visible(viewer_self, request.scope)
    visible_to = tuple(sorted(satisfying.audience | {request.subject}))

    entries: list[TimelineEntry] = []
    for i, sig in enumerate(signals):
        entries.append(
            TimelineEntry(
                entry_id=sig.entry_id or f"tl-{i}",
                subject=request.subject,
                kind=sig.kind,
                occurred_at=sig.occurred_at,
                summary=assert_plain_language(sig.summary),
                source_event_ids=tuple(sig.source_event_ids),
                permissions=PermissionControls(
                    consent_id=satisfying.consent_id,
                    visible_to=visible_to,
                    learner_controlled=True,
                    why_visible=why,
                ),
                topic_id=sig.topic_id,
                author_role=sig.author_role,
            )
        )

    entries.sort(key=lambda e: e.occurred_at)
    return LearnerTimeline(
        subject=request.subject,
        entries=tuple(entries),
        composed_at=asof,
        degraded_reasons=tuple(degraded_reasons or ()),
    )


__all__ = [
    "TimelineKind",
    "AUTHOR_LEARNER",
    "AUTHOR_TEACHER",
    "AUTHOR_SYSTEM",
    "TimelineEntry",
    "TimelineSignal",
    "LearnerTimeline",
    "compose_timeline",
]
