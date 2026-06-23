"""Surface hints — turn the profile into hints the onboarding + home can use.

The personalization profile is an internal, evidenced inference. A LEARNER must
never see the raw inference internals (the confidence scalars, the signal-id
lineage, the rule names). This module translates a gated profile into calm,
plain-language SURFACE HINTS the onboarding and home surfaces consume:

  - suggested subjects to surface first
  - a suggested goal to offer (never imposed)
  - a suggested pace
  - a single "why you're seeing this" line per hint (transparency without
    leaking internals)

Hard rules honoured here:

  - NO RAW INTERNALS to the learner. The hint carries a plain-language reason,
    never a confidence number, never the signal ids, never the rule. (A separate,
    gated explainability path can expose the full lineage to the learner about
    THEIR OWN profile — but the home/onboarding hint surface does not.)
  - SUGGESTIONS, NEVER DECISIONS. Hints are offered; the human chooses. Nothing
    here auto-fires a consequential action (permission ladder, INVARIANT 8).
  - CONFIDENCE-BANDED. Only sufficiently-confident traits become hints; a weak,
    barely-formed read is held back rather than shown as fact.
  - PII-FREE and brand-clean: plain language, no emoji, no exclamation marks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from .consent_gate import (
    ConsentScope,
    PersonalizationConsent,
    TraitKind,
    evaluate_inference,
)
from .infer import InferredTrait
from .profile import PersonalizationProfile

# A hint is shown only when the underlying trait clears this confidence floor.
# Below it, the read is too provisional to surface as a suggestion.
_HINT_CONFIDENCE_FLOOR = 0.3

# Brand discipline: no emoji, no exclamation marks in product copy.
_FORBIDDEN_COPY = re.compile(r"[!\U0001F000-\U0001FAFF☀-➿]")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def assert_brand_clean(text: str) -> str:
    """Guard: surface copy carries no emoji and no exclamation mark."""
    if _FORBIDDEN_COPY.search(text):
        raise ValueError(
            "Surface copy must be calm plain language: no emoji, no exclamation "
            "marks. Offending text: " + repr(text)
        )
    return text


@dataclass(frozen=True)
class Hint:
    """A single surface hint. Plain language only — no internals.

    ``value`` is the opaque/enumerated thing being suggested (a subject id, a goal
    value, a pace). ``why`` is the learner-facing transparency line. There is
    deliberately NO confidence field and NO evidence-id field on this object — the
    learner surface never sees them.
    """

    kind: str                  # "subject" | "goal" | "pace"
    value: str
    why: str

    def __post_init__(self) -> None:
        assert_brand_clean(self.why)


@dataclass(frozen=True)
class SurfaceHints:
    """The hints the onboarding + home surfaces consume.

    A learner-safe projection of the profile: suggested subjects, an optional
    suggested goal, an optional suggested pace, each with a plain-language reason.
    Carries NO confidence numbers, NO signal ids, NO rule names.
    """

    subject: str               # opaque canonical_uuid (for routing, not display)
    suggested_subjects: tuple[Hint, ...] = ()
    suggested_goal: Hint | None = None
    suggested_pace: Hint | None = None
    generated_at: datetime | None = None

    def is_empty(self) -> bool:
        return not (self.suggested_subjects or self.suggested_goal or self.suggested_pace)


def _passes_floor(trait: InferredTrait) -> bool:
    return trait.confidence >= _HINT_CONFIDENCE_FLOOR


def _subject_why() -> str:
    return "Suggested because of what you have spent time on so far."


def _goal_why() -> str:
    return "Offered from the direction your activity points toward. You can change it any time."


def _pace_why() -> str:
    return "Based on the rhythm of your recent sessions. You stay in control of this."


def to_surface_hints(
    profile: PersonalizationProfile,
    *,
    consents: Iterable[PersonalizationConsent],
    asof: datetime | None = None,
) -> SurfaceHints:
    """Translate a profile into learner-safe surface hints.

    GATED: hints are produced only when a live consent covers the
    ``preferences-hints`` scope; without it, an empty hint set is returned (the
    surfaces fall back to a neutral default). Raw inference internals never cross
    this boundary — the output carries plain language only.

    CONFIDENCE-BANDED: only traits above the hint floor become suggestions; a
    barely-formed read is withheld rather than shown.
    """
    asof = asof or _now()
    consents = list(consents)

    # The hints surface is itself consent-scoped. We reuse the gate with the
    # preferences-hints scope; if no permitted trait clears it, hints are empty.
    def hints_permitted(kind: TraitKind) -> bool:
        return evaluate_inference(
            subject=profile.subject,
            trait=kind,
            consents=consents,
            scope="preferences-hints",
            asof=asof,
        ).allowed

    subject_hints: list[Hint] = []
    for trait in profile.traits:
        if trait.kind not in (TraitKind.PREFERRED_SUBJECT, TraitKind.INTEREST):
            continue
        if not _passes_floor(trait) or not hints_permitted(trait.kind):
            continue
        # Avoid duplicate subject suggestions.
        if any(h.value == trait.value for h in subject_hints):
            continue
        subject_hints.append(Hint(kind="subject", value=trait.value, why=_subject_why()))

    goal_hint: Hint | None = None
    goal_trait = profile.trait(TraitKind.GOAL)
    if goal_trait and _passes_floor(goal_trait) and hints_permitted(TraitKind.GOAL):
        goal_hint = Hint(kind="goal", value=goal_trait.value, why=_goal_why())

    pace_hint: Hint | None = None
    pace_trait = profile.trait(TraitKind.PACE)
    if pace_trait and _passes_floor(pace_trait) and hints_permitted(TraitKind.PACE):
        pace_hint = Hint(kind="pace", value=pace_trait.value, why=_pace_why())

    return SurfaceHints(
        subject=profile.subject,
        suggested_subjects=tuple(subject_hints),
        suggested_goal=goal_hint,
        suggested_pace=pace_hint,
        generated_at=asof,
    )


__all__ = [
    "Hint",
    "SurfaceHints",
    "assert_brand_clean",
    "to_surface_hints",
]
