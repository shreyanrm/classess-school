"""Parent-specific FEEDBACK GENERATION (B9) — celebration / growth / next-step.

The dossier:

  the parent companion ... turns the child's own progress into a shareable,
  beautifully presented moment — converting anxiety into pride ... parent-specific
  feedback generation.

This generates parent feedback FROM REAL SIGNALS, not canned strings. The shape
is three parts:

  - **celebration** — a genuine win, grounded in an actual positive signal.
  - **growth** — an honest area to keep working on, framed as growth (never a
    verdict, never a raw score), grounded in a real signal.
  - **next_step** — one concrete thing to do WITH the child at home.

Two laws make this safe and real:

  1. **Generate-and-VERIFY (INVARIANT 7).** Each part is generated from the
     signals, then VERIFIED before it can be shown: a part is only kept if it is
     grounded in at least one supplied signal (no signal -> the part is withheld,
     not fabricated) AND it passes a confidence gate. A feedback set that cannot
     ground a celebration is honest about it rather than inventing one.
  2. **No canned strings / no raw numbers.** The generated text references the
     real signal's plain-language descriptor; it never emits a percentage or a
     bare metric, and the same input does not collapse to one fixed sentence — it
     is composed from the specific signals present.

Degrade-safe: with no orchestrator wired this composes the feedback
deterministically FROM the signals (a real generator would draft richer prose and
then pass the SAME verification gate). It reads no secret and makes no live call.

Import-safe: no I/O, no provider, no secret value read at import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class SignalKind(str, Enum):
    """The kind of real signal a feedback part can be grounded in."""

    STRENGTH = "strength"          # a genuine, observed strength -> celebration.
    GROWTH_AREA = "growth_area"    # an honest area to develop -> growth.
    HABIT = "habit"                # a working/learning habit -> next-step at home.
    PERSISTENCE = "persistence"    # showed effort through difficulty -> celebration.


@dataclass(frozen=True)
class ProgressSignal:
    """One real, plain-language signal about a child's progress. PII-free.

    ``descriptor`` is a plain-language phrase ("kept going through hard fraction
    problems"), NEVER a raw number. ``confidence`` is the upstream estimate's
    trust in the signal (0..1); the verification gate uses it.
    """

    kind: SignalKind
    subject: str               # plain subject/area label, e.g. "fractions".
    descriptor: str            # plain-language description of the signal.
    confidence: float          # 0..1 trust in this signal.


@dataclass(frozen=True)
class FeedbackPart:
    """One verified part of the parent feedback, with its provenance."""

    kind: Literal["celebration", "growth", "next_step"]
    text: str
    grounded_in: str           # the descriptor of the signal it is grounded in.
    confidence: float
    verified: bool


@dataclass
class ParentFeedback:
    """The generated, verified parent feedback. A part is absent when it could
    not be grounded — the set is honest, never padded with a fabricated part."""

    child_uuid: str
    celebration: FeedbackPart | None
    growth: FeedbackPart | None
    next_step: FeedbackPart | None
    # The plain-language reason any part was withheld (explainability).
    withheld_notes: tuple[str, ...] = field(default_factory=tuple)
    framing: Literal["celebration_growth_next_step"] = "celebration_growth_next_step"

    @property
    def parts(self) -> tuple[FeedbackPart, ...]:
        return tuple(p for p in (self.celebration, self.growth, self.next_step) if p)


# The confidence gate: a part below this is not shown (generate-and-verify).
DEFAULT_CONFIDENCE_GATE = 0.55


class ParentFeedbackGenerator:
    """Generates celebration/growth/next-step feedback from real signals, with a
    verification + confidence gate before anything can be shown."""

    def __init__(self, *, confidence_gate: float = DEFAULT_CONFIDENCE_GATE) -> None:
        self._gate = confidence_gate

    @property
    def confidence_gate(self) -> float:
        return self._gate

    def generate(
        self,
        *,
        child_uuid: str,
        signals: list[ProgressSignal],
    ) -> ParentFeedback:
        """Generate the three-part feedback from real signals.

        Each part is GENERATED from the best matching signal then VERIFIED: kept
        only if grounded in a real signal AND above the confidence gate. With no
        suitable signal, the part is withheld (and a note explains why) — never
        fabricated.
        """
        withheld: list[str] = []

        celebration = self._build_part(
            "celebration",
            signals,
            kinds=(SignalKind.STRENGTH, SignalKind.PERSISTENCE),
            withheld=withheld,
        )
        growth = self._build_part(
            "growth",
            signals,
            kinds=(SignalKind.GROWTH_AREA,),
            withheld=withheld,
        )
        next_step = self._build_part(
            "next_step",
            signals,
            kinds=(SignalKind.HABIT, SignalKind.GROWTH_AREA, SignalKind.STRENGTH),
            withheld=withheld,
        )

        return ParentFeedback(
            child_uuid=child_uuid,
            celebration=celebration,
            growth=growth,
            next_step=next_step,
            withheld_notes=tuple(withheld),
        )

    def _build_part(
        self,
        kind: Literal["celebration", "growth", "next_step"],
        signals: list[ProgressSignal],
        *,
        kinds: tuple[SignalKind, ...],
        withheld: list[str],
    ) -> FeedbackPart | None:
        # Pick the strongest-confidence signal of an eligible kind (generation
        # input). This makes the output specific to the signals present, not a
        # canned string.
        candidates = [s for s in signals if s.kind in kinds]
        if not candidates:
            withheld.append(
                f"{kind}: withheld — no real signal to ground it in; nothing is "
                "fabricated."
            )
            return None
        signal = max(candidates, key=lambda s: s.confidence)

        # Verification gate (generate-and-verify): below confidence -> withhold.
        if signal.confidence < self._gate:
            withheld.append(
                f"{kind}: withheld — the supporting signal did not clear the "
                f"confidence gate ({self._gate})."
            )
            return None

        text = self._compose(kind, signal)
        # Defence in depth: never let a raw number slip into shown feedback.
        if any(ch.isdigit() for ch in text) or "%" in text:
            withheld.append(f"{kind}: withheld — generated text carried a raw metric.")
            return None

        return FeedbackPart(
            kind=kind,
            text=text,
            grounded_in=signal.descriptor,
            confidence=signal.confidence,
            verified=True,
        )

    @staticmethod
    def _compose(
        kind: Literal["celebration", "growth", "next_step"],
        signal: ProgressSignal,
    ) -> str:
        """Compose the part's prose from the specific signal (degraded generator).

        Specific to the signal's subject + descriptor — not a fixed sentence. A
        real generator would draft richer prose and pass the same gate.
        """
        if kind == "celebration":
            return (
                f"Something to celebrate together: in {signal.subject}, your child "
                f"{signal.descriptor}. That is real and worth naming out loud."
            )
        if kind == "growth":
            return (
                f"An area to keep growing: {signal.subject} — {signal.descriptor}. "
                "This is a next stretch, not a setback, and it is very normal."
            )
        # next_step
        return (
            f"One thing to try at home: pick a calm few minutes and explore "
            f"{signal.subject} together — {signal.descriptor}. Letting them lead "
            "is what makes it stick."
        )
