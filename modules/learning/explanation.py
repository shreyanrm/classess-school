"""Selectable explanation styles for the REVEAL step (d12).

"Multiple explanation styles ... adapt to the learner." The reveal in
pose -> struggle -> REVEAL is never one-size-fits-all: the same idea lands
differently as a concrete worked example, a real-world analogy, a step-by-step
walk-through, the underlying intuition, a visual/spatial framing, or a
Socratic counter-question. This module is the small, deterministic chooser +
contract for those styles.

What it is:
  - a fixed catalogue of named EXPLANATION STYLES, each with a plain learner-
    facing label and the contract it satisfies (does it pose a question? does it
    work an example? does it lean visual?);
  - a learner PREFERENCE + a context-aware RECOMMENDATION (e.g. a fresh
    conceptual gap is better served by intuition/analogy than by another worked
    example; a procedural gap by a step-by-step walk-through), with the chosen
    style always explainable;
  - a guard that a SOCRATIC style still poses a question (it must not collapse
    into a lecture — the same anti-explain-first discipline as d12).

What it is NOT: it does not generate the explanation prose itself (that is the
content engine / ai-fabric, under generate-and-verify). It selects the STYLE and
carries the contract; the surface fills in the styled content. Pure, import-safe,
no PII, no provider, stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExplanationStyle(str, Enum):
    """The catalogue of selectable explanation styles for the reveal."""

    WORKED_EXAMPLE = "worked_example"     # a fully worked instance to study
    ANALOGY = "analogy"                   # a real-world comparison
    STEP_BY_STEP = "step_by_step"         # an ordered walk-through of the method
    INTUITION = "intuition"               # the underlying "why it works"
    VISUAL = "visual"                     # a diagram/number-line/spatial framing
    SOCRATIC = "socratic"                 # a guiding counter-question, not a telling


ALL_EXPLANATION_STYLES: tuple[ExplanationStyle, ...] = (
    ExplanationStyle.WORKED_EXAMPLE,
    ExplanationStyle.ANALOGY,
    ExplanationStyle.STEP_BY_STEP,
    ExplanationStyle.INTUITION,
    ExplanationStyle.VISUAL,
    ExplanationStyle.SOCRATIC,
)


@dataclass(frozen=True)
class StyleContract:
    """The contract one explanation style satisfies. Lets a surface know how to
    render it and lets verification enforce the right discipline (a Socratic reveal
    must pose; a worked example must work an instance)."""

    style: ExplanationStyle
    learner_label: str        # plain learner-facing prose (no formula, no emoji)
    poses_question: bool      # does this style end on a question for the learner?
    works_example: bool       # does it work a concrete instance?
    is_visual: bool           # does it lean on a diagram/spatial framing?


# The contract per style. Learner-facing labels are plain professional prose
# (CONFIDENTIALITY SCRUB: no formula, no emoji, no exclamation).
STYLE_CONTRACTS: dict[ExplanationStyle, StyleContract] = {
    ExplanationStyle.WORKED_EXAMPLE: StyleContract(
        ExplanationStyle.WORKED_EXAMPLE,
        "Here is one worked all the way through — follow each move, then try one yourself",
        poses_question=False, works_example=True, is_visual=False,
    ),
    ExplanationStyle.ANALOGY: StyleContract(
        ExplanationStyle.ANALOGY,
        "Here is an everyday comparison that works the same way",
        poses_question=False, works_example=False, is_visual=False,
    ),
    ExplanationStyle.STEP_BY_STEP: StyleContract(
        ExplanationStyle.STEP_BY_STEP,
        "Here is the method one step at a time",
        poses_question=False, works_example=True, is_visual=False,
    ),
    ExplanationStyle.INTUITION: StyleContract(
        ExplanationStyle.INTUITION,
        "Here is why this works underneath, before any procedure",
        poses_question=False, works_example=False, is_visual=False,
    ),
    ExplanationStyle.VISUAL: StyleContract(
        ExplanationStyle.VISUAL,
        "Here it is as a picture you can see and check",
        poses_question=False, works_example=False, is_visual=True,
    ),
    ExplanationStyle.SOCRATIC: StyleContract(
        ExplanationStyle.SOCRATIC,
        "Here is a question that points the way — what do you notice?",
        poses_question=True, works_example=False, is_visual=False,
    ),
}


# Which style best serves which gap type (from the gap taxonomy in
# :mod:`learning.practice`). A conceptual gap is best re-anchored with intuition or
# an analogy, NOT another worked example of the same form; a procedural gap wants a
# step-by-step walk-through; a language gap wants the plainest framing; and so on.
_GAP_STYLE: dict[str, ExplanationStyle] = {
    "conceptual": ExplanationStyle.INTUITION,
    "prerequisite": ExplanationStyle.STEP_BY_STEP,
    "procedural": ExplanationStyle.STEP_BY_STEP,
    "application": ExplanationStyle.ANALOGY,
    "retention": ExplanationStyle.WORKED_EXAMPLE,
    "language": ExplanationStyle.VISUAL,
    "accuracy": ExplanationStyle.STEP_BY_STEP,
    "speed": ExplanationStyle.WORKED_EXAMPLE,
    "confidence": ExplanationStyle.SOCRATIC,
    "support-dependency": ExplanationStyle.SOCRATIC,
}

# Default style when there is no gap signal and no learner preference: a worked
# example is the safest first reveal.
DEFAULT_STYLE = ExplanationStyle.WORKED_EXAMPLE


@dataclass(frozen=True)
class StyleChoice:
    """The chosen explanation style with its plain why (explainability)."""

    style: ExplanationStyle
    contract: StyleContract
    reason: str
    from_preference: bool     # True when the learner's stated preference was used


def _coerce_style(value: ExplanationStyle | str | None) -> ExplanationStyle | None:
    if value is None:
        return None
    if isinstance(value, ExplanationStyle):
        return value
    try:
        return ExplanationStyle(str(value))
    except ValueError:
        return None


def choose_style(
    *,
    gap_type: str | None = None,
    learner_preference: ExplanationStyle | str | None = None,
    last_style_used: ExplanationStyle | str | None = None,
) -> StyleChoice:
    """Choose the explanation style for the next reveal.

    Order of precedence, all explainable:
      1. A stated learner PREFERENCE wins — the learner knows how they learn —
         EXCEPT where the gap type makes that style counter-productive (e.g. a
         conceptual gap with a "worked example" preference still falls back to
         intuition: more of the same form will not move a conceptual gap).
      2. Otherwise the gap type selects the style (the taxonomy-aware mapping).
      3. Otherwise the default (a worked example), avoiding repeating the exact
         style just used so the reveal varies.
    """
    pref = _coerce_style(learner_preference)
    last = _coerce_style(last_style_used)

    # A conceptual gap is the one place a stated preference for "more worked
    # examples" is overridden: it will not shift a conceptual misunderstanding.
    conceptual_blocked = gap_type == "conceptual" and pref in (
        ExplanationStyle.WORKED_EXAMPLE,
        ExplanationStyle.STEP_BY_STEP,
    )

    if pref is not None and not conceptual_blocked:
        return StyleChoice(
            style=pref,
            contract=STYLE_CONTRACTS[pref],
            reason="Using your preferred explanation style.",
            from_preference=True,
        )

    if gap_type and gap_type in _GAP_STYLE:
        style = _GAP_STYLE[gap_type]
        if conceptual_blocked:
            reason = (
                "A conceptual gap does not shift with another example, so this "
                "reveal leads with the underlying idea instead."
            )
        else:
            reason = f"This style suits a {gap_type} gap best."
        return StyleChoice(
            style=style, contract=STYLE_CONTRACTS[style], reason=reason, from_preference=False
        )

    # No gap, no usable preference: default, but vary from the last one shown.
    style = DEFAULT_STYLE
    if last == DEFAULT_STYLE:
        style = ExplanationStyle.INTUITION
    return StyleChoice(
        style=style,
        contract=STYLE_CONTRACTS[style],
        reason="No specific gap to target — a clear default reveal, varied from last time.",
        from_preference=False,
    )


def assert_socratic_poses(text: str, *, style: ExplanationStyle) -> None:
    """Guard: a SOCRATIC reveal must actually pose a question — it must not
    collapse into a lecture. Mirrors the d12 anti-explain-first discipline. No-op
    for non-Socratic styles."""
    if style is ExplanationStyle.SOCRATIC and "?" not in text:
        raise ValueError(
            "a Socratic explanation must pose a question (no '?' found); it must "
            "guide by asking, not by telling."
        )
