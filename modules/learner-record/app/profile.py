"""The evidence-linked learner profile (B8) — the School-facing composition.

This is the read view a School surface renders: per topic, in PLAIN LANGUAGE,
whether the learner can do it INDEPENDENTLY or only WITH SUPPORT, the gaps that
matter, and — on every single item — its SOURCE (the evidence behind it) and its
PERMISSION CONTROLS (who consented, who can see it, why it is visible).

Hard rules honoured here:

  - PLAIN LANGUAGE ONLY. The composite mastery number and the six-dimension
    formula are spine concerns and are NEVER surfaced. This module reads the
    plain-language band and renders a sentence. The renderers go further and
    assert no digit/percent/formula leaks into learner/parent-facing text.
  - INDEPENDENT vs SUPPORT-DEPENDENT, not a score. The keystone read is whether
    a topic is held independently or is still support-dependent.
  - EVERY ITEM LINKS TO EVIDENCE. No profile item exists without its source
    event-id lineage; evidence over assertion (principle 7).
  - GATED. The profile is assembled only behind the consent + purpose gate
    (access.require). A read without a satisfied consent check is denied.
  - PII-FREE. Keyed by opaque ``canonical_uuid`` and opaque topic ids only.

B8 does NOT author mastery (that is CORE, spine A3). It COMPOSES governed reads
into a School-facing record. The mastery band + plain language + gaps arrive
already-derived from the governed view; this module shapes and gates them and
never recomputes a number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Literal

from .access import ConsentGrant, ReadRequest, require

# The plain-language bands as they arrive from the governed mastery view
# (contracts/src/events/mastery.ts MasteryBand). We display them; we never
# compute them and never show the composite they were derived from.
MasteryBand = Literal["not-started", "emerging", "developing", "secure", "independent"]

# The two states the School record foregrounds — independence is the goal, and
# everything short of independent is, by definition, still support-dependent.
IndependenceState = Literal["independent", "support-dependent", "not-started"]

# Plain-language phrasing per band. No number, no percentage, no formula — ever.
_BAND_PHRASING: dict[MasteryBand, str] = {
    "not-started": "has not started this yet",
    "emerging": "is starting to show the idea, with a lot of support",
    "developing": "can do this with guidance, not yet on their own",
    "secure": "is reliable here but not yet fully on their own",
    "independent": "can do this on their own",
}

# Numbers, percentages, and formula symbols that must never reach a
# learner/parent-facing string. The guard below rejects them.
_FORBIDDEN_IN_PLAIN_TEXT = re.compile(r"[0-9]|%|[×x]\s|=|\^|product of")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def assert_plain_language(text: str) -> str:
    """Guard: a learner/parent-facing string must carry NO number, percentage,
    or formula. Returns the text unchanged when clean; raises otherwise.

    This is the load-bearing check behind "plain-language output never leaks a
    number or formula" — used at the boundary so a regression is caught in code,
    not just in review. The lone allowed exception is the word "on their own",
    which contains no digit.
    """
    if _FORBIDDEN_IN_PLAIN_TEXT.search(text):
        raise ValueError(
            "Plain-language text must not contain a number, percentage, or "
            "formula (it leaks the mastery scalar). Offending text: "
            + repr(text)
        )
    return text


def independence_state_of(band: MasteryBand) -> IndependenceState:
    """Collapse a band to the School record's foreground read."""
    if band == "not-started":
        return "not-started"
    if band == "independent":
        return "independent"
    return "support-dependent"


@dataclass(frozen=True)
class EvidenceSource:
    """The provenance of one profile item — its evidence lineage.

    Every profile item carries one of these (principle 7: evidence over
    assertion). The event-ids are opaque references into the immutable store;
    following them is itself a gated ``evidence-lineage`` read.
    """

    source_event_ids: tuple[str, ...]
    last_evidence_at: datetime | None
    observation_count: int

    def __post_init__(self) -> None:
        if not self.source_event_ids:
            raise ValueError(
                "A profile item must link to at least one source event — no "
                "item exists without evidence (evidence over assertion)."
            )


@dataclass(frozen=True)
class PermissionControls:
    """Who consented to this item being shown, and to whom.

    Surfaces render this as the "why am I seeing this" affordance and as the
    learner's control over their own record. Opaque ids only.
    """

    consent_id: str
    visible_to: tuple[str, ...]            # opaque viewer ids in the audience
    learner_controlled: bool = True        # the learner can revoke visibility
    why_visible: str = ""                   # plain-language explanation


@dataclass(frozen=True)
class GapNote:
    """A plain-language note about a gap, with its lineage. Never a number."""

    gap_type: str
    plain_language: str                     # the human "what to do", no number
    confirmed: bool
    source_event_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        assert_plain_language(self.plain_language)
        if not self.source_event_ids:
            raise ValueError("A gap note must link to its evidence events.")


@dataclass(frozen=True)
class ProfileItem:
    """One topic on the School-facing record: plain language + independence
    state + its source + its permission controls + plain-language gap notes.

    There is NO mastery number field anywhere on this object by design.
    """

    topic_id: str
    independence: IndependenceState
    plain_language: str                     # learner-safe sentence, no number
    source: EvidenceSource
    permissions: PermissionControls
    gaps: tuple[GapNote, ...] = ()

    def __post_init__(self) -> None:
        assert_plain_language(self.plain_language)


@dataclass(frozen=True)
class LearnerRecordProfile:
    """The composed, gated, plain-language profile for one learner."""

    subject: str                            # opaque canonical_uuid
    items: tuple[ProfileItem, ...]
    composed_at: datetime
    degraded_reasons: tuple[str, ...] = ()

    def item(self, topic_id: str) -> ProfileItem | None:
        for it in self.items:
            if it.topic_id == topic_id:
                return it
        return None

    @property
    def independent_topics(self) -> tuple[ProfileItem, ...]:
        return tuple(i for i in self.items if i.independence == "independent")

    @property
    def support_dependent_topics(self) -> tuple[ProfileItem, ...]:
        """The topics the learner can only do WITH help — the gap the
        Independence dimension exists to surface, foregrounded for the School."""
        return tuple(i for i in self.items if i.independence == "support-dependent")


@dataclass(frozen=True)
class GovernedTopicView:
    """One topic as it arrives from the governed mastery read view (A3).

    This is the INPUT shape — what a consent + purpose-gated read of the learner
    graph returns. It carries the already-derived band and gaps plus lineage; it
    NEVER carries the composite number (the governed view omits it for display
    consumers). B8 composes these into ``ProfileItem``s; it never recomputes.
    """

    topic_id: str
    band: MasteryBand
    source_event_ids: tuple[str, ...]
    last_evidence_at: datetime | None = None
    observation_count: int = 0
    gaps: tuple[GapNote, ...] = ()


def _why_visible_for(viewer_self: bool, scope: str) -> str:
    if viewer_self:
        return "This is your own record."
    return f"The learner consented to share their {scope.replace('-', ' ')} with you."


def compose_profile(
    views: Iterable[GovernedTopicView],
    *,
    request: ReadRequest,
    grants: Iterable[ConsentGrant],
    asof: datetime | None = None,
    degraded_reasons: Iterable[str] | None = None,
) -> LearnerRecordProfile:
    """Compose the School-facing profile from governed topic views.

    GATED FIRST: the consent + purpose check runs before any view is read. A
    read without a satisfied consent check raises ``ConsentDenied`` and no
    profile is built. The request scope must be ``mastery-profile``.

    Each governed view becomes a ``ProfileItem`` in plain language, carrying its
    source lineage and the permission controls derived from the satisfying
    grant. No number ever lands on the output.
    """
    asof = asof or _now()
    grants = list(grants)

    # DENIED-BY-DEFAULT: assemble nothing until the gate allows the read.
    access = require(request, grants, asof=asof)

    satisfying = next(g for g in grants if g.consent_id == access.consent_id)
    viewer_self = request.viewer == request.subject
    why = _why_visible_for(viewer_self, request.scope)
    visible_to = tuple(sorted(satisfying.audience | ({request.subject})))

    items: list[ProfileItem] = []
    for view in views:
        band = view.band
        state = independence_state_of(band)
        sentence = f"The learner {_BAND_PHRASING[band]}."
        item = ProfileItem(
            topic_id=view.topic_id,
            independence=state,
            plain_language=assert_plain_language(sentence),
            source=EvidenceSource(
                source_event_ids=tuple(view.source_event_ids),
                last_evidence_at=view.last_evidence_at,
                observation_count=view.observation_count,
            ),
            permissions=PermissionControls(
                consent_id=satisfying.consent_id,
                visible_to=visible_to,
                learner_controlled=True,
                why_visible=why,
            ),
            gaps=tuple(view.gaps),
        )
        items.append(item)

    return LearnerRecordProfile(
        subject=request.subject,
        items=tuple(items),
        composed_at=asof,
        degraded_reasons=tuple(degraded_reasons or ()),
    )


__all__ = [
    "MasteryBand",
    "IndependenceState",
    "assert_plain_language",
    "independence_state_of",
    "EvidenceSource",
    "PermissionControls",
    "GapNote",
    "ProfileItem",
    "LearnerRecordProfile",
    "GovernedTopicView",
    "compose_profile",
]
