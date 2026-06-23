"""The assistance-ladder controller (B7).

The ladder, most support to none:

    Learn -> Coach -> Hint -> Work-with-me -> Check-my-work -> Independent

The rungs themselves are the single source of truth in the evidence contract
(``contracts/src/assistance`` re-exporting ``events/attempt`` AssistanceLevel).
This controller does NOT redefine them — it ports the SAME ordered ladder and
the SAME helping-vs-evaluating classification, and adds the B7 behavior:

  - FADE support as competence rises. The recommended rung is a function of the
    learner's current mastery on the topic: the stronger and more INDEPENDENT
    the evidence, the lower on the ladder (less help) we offer next. Support is
    never yanked away in one step — fading is one rung at a time, and a fresh
    struggle can step support back up one rung.
  - ALWAYS tell the learner whether the system is HELPING or EVALUATING. Only
    the Independent rung is an unaided demonstration (``evaluating``); every
    other rung — including Check-my-work — is HELPING and produces SUPPORTED
    evidence about what the learner can do WITH help.

A rung maps deterministically to the attempt ``mode``: only ``Independent`` is
``mode = independent``; every other rung is ``supported``. This is the keystone
coherence the attempt contract enforces, mirrored here so the flow controller
never constructs an incoherent attempt.

Pure and import-safe: no I/O, no provider, no pydantic needed to use the
ladder logic. Mastery is consumed as a plain band string + independence float
so this stays decoupled from the engine's concrete result type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# The ladder in order, most support to none. Mirrors
# contracts/src/assistance/index.ts ASSISTANCE_LADDER exactly — do not reorder.
ASSISTANCE_LADDER: tuple[str, ...] = (
    "Learn",
    "Coach",
    "Hint",
    "Work-with-me",
    "Check-my-work",
    "Independent",
)

AssistanceRung = Literal[
    "Learn", "Coach", "Hint", "Work-with-me", "Check-my-work", "Independent"
]
AssistanceMode = Literal["helping", "evaluating"]
AttemptMode = Literal["independent", "supported"]

# Plain-language, learner-facing description of each rung. Never the formula,
# never a raw number — clean professional prose (CONFIDENTIALITY SCRUB).
RUNG_LEARNER_LABEL: dict[str, str] = {
    "Learn": "I will walk you through it",
    "Coach": "I will guide you step by step",
    "Hint": "I will nudge you if you get stuck",
    "Work-with-me": "We will build the answer together",
    "Check-my-work": "You do it, then I check it",
    "Independent": "You do this on your own",
}

# Whether the system is HELPING or EVALUATING at this rung, said plainly to the
# learner so they always know which it is.
RUNG_MODE_LABEL: dict[AssistanceMode, str] = {
    "helping": "I am helping you here.",
    "evaluating": "This one is on your own, so it shows what you can do unaided.",
}


def rung_index(rung: str) -> int:
    """Position on the ladder (0 = most support, 5 = none). Mirrors
    assistanceRungIndex in the contract. Unknown rung -> 0 (most support), the
    safe default — never assume more independence than is evidenced."""
    try:
        return ASSISTANCE_LADDER.index(rung)
    except ValueError:
        return 0


def assistance_mode_of(rung: str) -> AssistanceMode:
    """Helping vs evaluating. Only ``Independent`` is evaluating; every other
    rung — including Check-my-work — is helping (mirrors the contract)."""
    return "evaluating" if rung == "Independent" else "helping"


def is_unaided_demonstration(rung: str) -> bool:
    """True only for ``Independent`` — the only rung whose evidence can confirm
    independent mastery."""
    return rung == "Independent"


def attempt_mode_of(rung: str) -> AttemptMode:
    """The attempt ``mode`` this rung produces. Keystone coherence: only
    ``Independent`` -> ``independent``; every other rung -> ``supported`` (the
    attempt contract rejects any other pairing)."""
    return "independent" if rung == "Independent" else "supported"


# Band -> the rung we are willing to START a learner at on a topic. As mastery
# rises (band climbs), the starting offer moves DOWN the ladder (less help).
# This is the fade. A learner with no evidence starts fully supported.
_BAND_START_RUNG: dict[str, str] = {
    "not-started": "Learn",
    "emerging": "Coach",
    "developing": "Hint",
    "secure": "Check-my-work",
    "independent": "Independent",
}

# Independence floor below which we will NOT offer the Independent rung as the
# starting point regardless of band — independence must be earned, and the
# keystone read is never assumed. Mirrors the engine's _INDEPENDENT_FLAG_FLOOR.
_INDEPENDENT_OFFER_FLOOR = 0.55


@dataclass(frozen=True)
class LadderState:
    """The current rung offer for one (learner, topic), with the plain-language
    declaration of whether the system is helping or evaluating.

    ``rung`` is what we offer next; ``mode`` is helping/evaluating; ``attempt_mode``
    is the coherent attempt mode the flow controller must stamp; the labels are
    learner-facing prose.
    """

    rung: AssistanceRung
    mode: AssistanceMode
    attempt_mode: AttemptMode
    rung_label: str
    mode_declaration: str
    fading: bool  # True when this offer is LESS help than the learner last used.

    @property
    def index(self) -> int:
        return rung_index(self.rung)


def _clamp_rung(rung: str) -> str:
    if rung not in ASSISTANCE_LADDER:
        return "Learn"
    return rung


def recommend_rung(
    *,
    band: str,
    independence: float,
    last_rung_used: str | None = None,
    recent_struggle: bool = False,
) -> str:
    """Choose the assistance rung to OFFER next, fading support as competence
    grows. Pure function of the learner's current state.

    Rules (the fade):
      - Start from the band's natural rung (more help for weaker bands).
      - Never offer ``Independent`` until independence clears the floor — the
        keystone read is earned, not assumed.
      - Fade at most ONE rung at a time relative to the last rung actually used,
        so support is withdrawn gradually, never yanked.
      - A recent genuine struggle steps support back UP one rung (more help),
        so the ladder responds to difficulty in the moment.
    """
    target = _clamp_rung(_BAND_START_RUNG.get(band, "Learn"))

    # Independence gate on the top rung.
    if target == "Independent" and independence < _INDEPENDENT_OFFER_FLOOR:
        target = "Check-my-work"

    target_idx = rung_index(target)

    if last_rung_used is not None and last_rung_used in ASSISTANCE_LADDER:
        last_idx = rung_index(last_rung_used)
        # Fade gradually: move toward the target but at most one rung down.
        if target_idx > last_idx:
            target_idx = last_idx + 1
        # A fresh struggle steps support back up one rung (toward more help).
        if recent_struggle:
            target_idx = max(0, min(last_idx, target_idx) - 1)

    # Re-apply the independence gate after stepping (never crest the floor).
    if target_idx == rung_index("Independent") and independence < _INDEPENDENT_OFFER_FLOOR:
        target_idx = rung_index("Check-my-work")

    target_idx = max(0, min(target_idx, len(ASSISTANCE_LADDER) - 1))
    return ASSISTANCE_LADDER[target_idx]


def next_state(
    *,
    band: str,
    independence: float,
    last_rung_used: str | None = None,
    recent_struggle: bool = False,
) -> LadderState:
    """Full ladder state for the next attempt: the offered rung plus the
    learner-facing declaration of helping-vs-evaluating.

    The system ALWAYS declares which mode it is in — this object carries the
    plain-language statement the surface shows verbatim.
    """
    rung = recommend_rung(
        band=band,
        independence=independence,
        last_rung_used=last_rung_used,
        recent_struggle=recent_struggle,
    )
    mode = assistance_mode_of(rung)
    fading = (
        last_rung_used is not None
        and last_rung_used in ASSISTANCE_LADDER
        and rung_index(rung) > rung_index(last_rung_used)
    )
    return LadderState(
        rung=rung,  # type: ignore[arg-type]
        mode=mode,
        attempt_mode=attempt_mode_of(rung),
        rung_label=RUNG_LEARNER_LABEL[rung],
        mode_declaration=RUNG_MODE_LABEL[mode],
        fading=fading,
    )


def coherent_attempt_fields(rung: str) -> tuple[AttemptMode, str]:
    """The (mode, assistance_level) pair the attempt contract requires for this
    rung. Use this when constructing an attempt so the coherence superRefine in
    the contract never rejects it."""
    return attempt_mode_of(rung), _clamp_rung(rung)
