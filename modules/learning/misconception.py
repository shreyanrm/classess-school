"""Misconception detonation (d12) — surface the contradiction, do not lecture.

When a learner gets a question wrong, the wrong answer is not noise: it is the
visible tip of a stable, often coherent WRONG RULE the learner is applying
faithfully. Telling them the right answer does not dislodge that rule — they will
reapply it on the next item. This module does the harder thing:

  1. INFER the likely misconception behind a specific wrong answer (the wrong
     rule the learner appears to be running), with a confidence and the evidence
     that points to it.
  2. ENGINEER A COUNTEREXAMPLE — a second, carefully chosen instance on which the
     learner's own wrong rule predicts an answer that is *visibly, checkably*
     wrong, so the contradiction surfaces from the learner's side. The
     counterexample is POSED as a question for the learner to attempt; it is
     NEVER a lecture, never the corrected explanation, never "actually, the rule
     is...". The whole point is that the learner runs into the wall themselves.

Why pose, not lecture (B7 — pose -> struggle -> reveal): a counterexample that
the learner works through produces durable conceptual change; a paragraph of
correction produces a nod and no change. So every artefact this module emits is
a PROMPT, with the lecture path deliberately closed off.

What this module is NOT:
  - It does not author mastery (CORE — the intelligence engine owns that). It
    reads ONE attempt's wrong answer and proposes a targeted next move.
  - It does not assert a misconception is CONFIRMED from a single attempt
    (INVARIANT 7 / principle 7 — no permanent judgment from one interaction).
    A single wrong answer yields a PROPOSED misconception and a probe; only
    repeated, consistent evidence (which the CORE engine confirms) escalates it.
  - It holds no credentials, makes no network call, needs no LLM. The detectors
    here are deterministic and run offline. A live model could later PROPOSE
    additional candidates through the ai-fabric generate-and-verify path, but a
    served counterexample must still pass a deterministic check (the engineered
    counterexample is itself a checkable arithmetic claim), so nothing
    fabricated is ever posed as truth.

Import-safe and pure: no I/O, no provider, no pydantic. Carries only opaque
ontology ids and the (already opaque) attempt — never PII (INVARIANT 1 + 2).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Sequence


# ---------------------------------------------------------------------------
# The attempt view this module reads
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WrongAttempt:
    """The minimal, PII-free view of one wrong attempt this module reasons over.

    ``stimulus`` is the question as posed (e.g. an arithmetic expression or a
    short prompt). ``learner_answer`` is what the learner produced;
    ``correct_answer`` is the key. Numeric answers drive the deterministic
    detectors; ``operands``/``operator`` are optional structured hints that make
    detection sharper when the surface already parsed the item.
    """

    topic_id: str
    stimulus: str
    learner_answer: str
    correct_answer: str
    operands: tuple[float, ...] = ()
    operator: str | None = None
    question_id: str | None = None

    @property
    def learner_value(self) -> float | None:
        return _to_number(self.learner_answer)

    @property
    def correct_value(self) -> float | None:
        return _to_number(self.correct_answer)


def _to_number(text: str) -> float | None:
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    # A leading fraction like "1/2".
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)\s*", s)
    if m:
        num, den = float(m.group(1)), float(m.group(2))
        return num / den if den != 0 else None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Misconception taxonomy (proposed labels, not a permanent judgment)
# ---------------------------------------------------------------------------

class MisconceptionKind(str, Enum):
    """A library of recurring, well-documented misconception families.

    These are LABELS for the wrong rule, not verdicts about the learner. The
    label exists so the counterexample can be engineered against the specific
    wrong rule rather than against "being wrong" in general.
    """

    # Adds numerators and denominators straight across: a/b + c/d -> (a+c)/(b+d).
    FRACTION_ADD_ACROSS = "fraction_add_across"
    # "Multiplication always makes bigger / division always makes smaller."
    MULT_ALWAYS_INCREASES = "mult_always_increases"
    # Longer decimal = larger number ("0.45 > 0.5 because 45 > 5").
    LONGER_DECIMAL_IS_LARGER = "longer_decimal_is_larger"
    # Distributes over the wrong thing, e.g. (a+b)^2 -> a^2 + b^2.
    FAULTY_DISTRIBUTION = "faulty_distribution"
    # Drops/ignores a negative sign or treats subtraction as commutative.
    SIGN_OR_ORDER_ERROR = "sign_or_order_error"
    # Place-value / carrying slip in multi-digit arithmetic.
    PLACE_VALUE_SLIP = "place_value_slip"
    # A wrong rule we could not pin to a known family from one attempt.
    UNCLASSIFIED = "unclassified"


# Plain-language, learner-NEUTRAL description of the wrong rule. Used for the
# teacher/audit surface, never shown to the learner as a correction. No emoji,
# no exclamation marks (product-copy law).
KIND_DESCRIPTION: dict[MisconceptionKind, str] = {
    MisconceptionKind.FRACTION_ADD_ACROSS: (
        "Treats fraction addition as adding numerators and denominators "
        "separately (a/b + c/d read as (a+c)/(b+d))."
    ),
    MisconceptionKind.MULT_ALWAYS_INCREASES: (
        "Assumes multiplying always produces a larger result and dividing a "
        "smaller one, which fails for factors between zero and one."
    ),
    MisconceptionKind.LONGER_DECIMAL_IS_LARGER: (
        "Compares decimals by digit count rather than place value, so a longer "
        "decimal is read as the larger number."
    ),
    MisconceptionKind.FAULTY_DISTRIBUTION: (
        "Distributes an exponent or operation across a sum, e.g. squaring each "
        "term of (a+b) separately."
    ),
    MisconceptionKind.SIGN_OR_ORDER_ERROR: (
        "Drops a sign or treats a non-commutative operation as if order does "
        "not matter."
    ),
    MisconceptionKind.PLACE_VALUE_SLIP: (
        "A carrying or place-value step is mishandled in multi-digit work."
    ),
    MisconceptionKind.UNCLASSIFIED: (
        "A consistent wrong rule appears to be in play but a single attempt is "
        "not enough to name the family."
    ),
}


# ---------------------------------------------------------------------------
# Detection result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MisconceptionHypothesis:
    """A PROPOSED misconception behind one wrong answer.

    Never a confirmed verdict — ``confirmed`` is always False here by design; a
    single attempt cannot confirm (principle 7). The CORE engine confirms across
    repeated evidence. ``confidence`` reflects how cleanly the wrong answer
    matches the wrong rule's prediction.
    """

    kind: MisconceptionKind
    confidence: float                 # in [0,1] — single-attempt strength only
    evidence: str                     # plain why-this-hypothesis, no PII
    predicted_wrong_answer: float | None  # what the wrong rule predicts here
    confirmed: bool = False           # always False from one attempt

    @property
    def is_classified(self) -> bool:
        return self.kind is not MisconceptionKind.UNCLASSIFIED


# A detector takes the wrong attempt and returns a hypothesis if its wrong rule
# reproduces the learner's answer, else None. Detectors are pure functions.
Detector = Callable[[WrongAttempt], "MisconceptionHypothesis | None"]


# ---------------------------------------------------------------------------
# Deterministic detectors — each models ONE wrong rule and checks whether it
# reproduces the learner's actual answer. A wrong rule that reproduces the
# answer is far stronger evidence than "the answer was wrong".
# ---------------------------------------------------------------------------

def _close(a: float | None, b: float | None, tol: float = 1e-6) -> bool:
    return a is not None and b is not None and math.isclose(a, b, rel_tol=tol, abs_tol=tol)


def _parse_two_fractions(stimulus: str) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Parse 'a/b + c/d' -> ((a,b),(c,d)). Only the add-across pattern."""
    m = re.fullmatch(
        r"\s*(-?\d+)\s*/\s*(-?\d+)\s*\+\s*(-?\d+)\s*/\s*(-?\d+)\s*", stimulus
    )
    if not m:
        return None
    a, b, c, d = (int(m.group(i)) for i in range(1, 5))
    if b == 0 or d == 0:
        return None
    return (float(a), float(b)), (float(c), float(d))


def detect_fraction_add_across(attempt: WrongAttempt) -> MisconceptionHypothesis | None:
    parsed = _parse_two_fractions(attempt.stimulus)
    if parsed is None:
        return None
    (a, b), (c, d) = parsed
    across_den = b + d
    if across_den == 0:
        return None
    predicted = (a + c) / across_den  # the WRONG rule's prediction
    if _close(attempt.learner_value, predicted):
        return MisconceptionHypothesis(
            kind=MisconceptionKind.FRACTION_ADD_ACROSS,
            confidence=0.8,
            evidence=(
                f"The answer matches adding straight across: "
                f"({int(a)}+{int(c)})/({int(b)}+{int(d)}) = {predicted:g}."
            ),
            predicted_wrong_answer=predicted,
        )
    return None


def detect_longer_decimal_is_larger(attempt: WrongAttempt) -> MisconceptionHypothesis | None:
    """For a 'which is larger, x or y?' decimal comparison answered with the
    longer-but-smaller decimal."""
    m = re.search(r"(-?\d*\.\d+)\D+(-?\d*\.\d+)", attempt.stimulus)
    if m is None:
        return None
    x, y = float(m.group(1)), float(m.group(2))
    chosen = _to_number(attempt.learner_answer)
    if chosen is None:
        return None
    # The learner chose a value; was it the one with MORE decimal digits but a
    # SMALLER value?
    digits = lambda s: len(s.split(".")[1]) if "." in s else 0
    longer = m.group(1) if digits(m.group(1)) > digits(m.group(2)) else m.group(2)
    longer_val = float(longer)
    smaller_val = min(x, y)
    if _close(chosen, longer_val) and _close(longer_val, smaller_val) and x != y:
        return MisconceptionHypothesis(
            kind=MisconceptionKind.LONGER_DECIMAL_IS_LARGER,
            confidence=0.75,
            evidence=(
                f"The chosen value {longer_val:g} has more decimal digits but is "
                f"the smaller number — comparison by digit count, not place value."
            ),
            predicted_wrong_answer=longer_val,
        )
    return None


def detect_mult_always_increases(attempt: WrongAttempt) -> MisconceptionHypothesis | None:
    """An item like 'n * f' with 0<f<1 where the learner answered with something
    >= n (expecting multiplication to increase)."""
    if attempt.operator != "*" or len(attempt.operands) != 2:
        return None
    n, f = attempt.operands
    lv = attempt.learner_value
    cv = attempt.correct_value
    if lv is None:
        return None
    # The misconception only bites when a factor is between 0 and 1 and the true
    # product is SMALLER than n, yet the learner produced something >= n.
    if 0 < f < 1 and n > 0 and cv is not None and cv < n and lv >= n:
        return MisconceptionHypothesis(
            kind=MisconceptionKind.MULT_ALWAYS_INCREASES,
            confidence=0.65,
            evidence=(
                f"A factor between 0 and 1 ({f:g}) makes the product smaller, but "
                f"the answer is at least the original {n:g} — multiplication treated "
                f"as always increasing."
            ),
            predicted_wrong_answer=lv,
        )
    return None


def detect_sign_or_order_error(attempt: WrongAttempt) -> MisconceptionHypothesis | None:
    """Subtraction answered as if commutative, or a flipped sign."""
    if attempt.operator != "-" or len(attempt.operands) != 2:
        return None
    a, b = attempt.operands
    lv = attempt.learner_value
    if lv is None:
        return None
    reversed_result = b - a              # treated subtraction as commutative
    flipped_sign = -(a - b)             # same magnitude, wrong sign
    if _close(lv, reversed_result) and a != b:
        return MisconceptionHypothesis(
            kind=MisconceptionKind.SIGN_OR_ORDER_ERROR,
            confidence=0.7,
            evidence=(
                f"The answer equals {b:g} - {a:g}, the operands subtracted in the "
                f"wrong order — subtraction treated as if order does not matter."
            ),
            predicted_wrong_answer=reversed_result,
        )
    if _close(lv, flipped_sign) and (a - b) != 0:
        return MisconceptionHypothesis(
            kind=MisconceptionKind.SIGN_OR_ORDER_ERROR,
            confidence=0.6,
            evidence="The answer has the right magnitude but the wrong sign.",
            predicted_wrong_answer=flipped_sign,
        )
    return None


def detect_faulty_distribution(attempt: WrongAttempt) -> MisconceptionHypothesis | None:
    """(a+b)^2 answered as a^2 + b^2."""
    m = re.fullmatch(r"\s*\(\s*(-?\d+)\s*\+\s*(-?\d+)\s*\)\s*\^?\s*2\s*", attempt.stimulus)
    if m is None:
        return None
    a, b = float(m.group(1)), float(m.group(2))
    predicted = a * a + b * b
    if _close(attempt.learner_value, predicted):
        return MisconceptionHypothesis(
            kind=MisconceptionKind.FAULTY_DISTRIBUTION,
            confidence=0.75,
            evidence=(
                f"The answer matches squaring each term separately: "
                f"{int(a)}^2 + {int(b)}^2 = {predicted:g}, missing the cross term."
            ),
            predicted_wrong_answer=predicted,
        )
    return None


# The detector battery, in priority order (most specific wrong rules first).
DEFAULT_DETECTORS: tuple[Detector, ...] = (
    detect_fraction_add_across,
    detect_faulty_distribution,
    detect_longer_decimal_is_larger,
    detect_sign_or_order_error,
    detect_mult_always_increases,
)


def identify_misconception(
    attempt: WrongAttempt,
    *,
    detectors: Sequence[Detector] = DEFAULT_DETECTORS,
) -> MisconceptionHypothesis:
    """Infer the likely misconception behind one wrong answer.

    Runs each deterministic detector; the strongest-matching wrong rule wins. If
    no known wrong rule reproduces the learner's answer, returns an UNCLASSIFIED
    hypothesis (low confidence) — we never invent a specific wrong rule we cannot
    evidence. A correct attempt raises ValueError: there is nothing to detonate.
    """
    if _close(attempt.learner_value, attempt.correct_value):
        raise ValueError(
            "identify_misconception requires a WRONG attempt; this answer is correct."
        )
    candidates = [h for d in detectors if (h := d(attempt)) is not None]
    if candidates:
        candidates.sort(key=lambda h: h.confidence, reverse=True)
        return candidates[0]
    return MisconceptionHypothesis(
        kind=MisconceptionKind.UNCLASSIFIED,
        confidence=0.2,
        evidence=(
            "The answer is wrong but does not match a known wrong-rule family "
            "from this single attempt; gather another attempt before naming it."
        ),
        predicted_wrong_answer=None,
    )


# ---------------------------------------------------------------------------
# The engineered counterexample — POSED, never lectured.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Counterexample:
    """An engineered counterexample, posed as a question.

    The counterexample is chosen so that the learner's own wrong rule predicts a
    ``predicted_under_misconception`` value that is visibly different from the
    ``actual_answer`` — and the prompt asks the learner to compute it, so the
    contradiction surfaces from their side. ``deterministic_check`` is the
    arithmetic claim a verifier (e.g. ai-fabric's real verifier) can re-run, so a
    served counterexample is never fabricated.

    NO field carries the corrected rule or an explanation. ``prompt`` is a
    question. ``is_lecture`` is structurally False; :func:`assert_not_a_lecture`
    enforces it.
    """

    misconception: MisconceptionKind
    prompt: str                        # the question posed to the learner
    counter_stimulus: str              # the engineered item (also a checkable expr)
    actual_answer: float               # the deterministically-true answer
    predicted_under_misconception: float  # what the wrong rule predicts here
    follow_up_question: str            # a second posing, still not a lecture
    deterministic_check: dict[str, object]  # {expression, claimed_answer} for verify
    rationale: str                     # teacher/audit-facing why-this-counterexample

    @property
    def probe(self) -> str:
        """Alias for the posed question — the probe shown to the learner."""
        return self.prompt

    @property
    def surfaces_contradiction(self) -> bool:
        """True iff the wrong rule and the truth disagree on this item — the
        whole point. A counterexample that does not split them is useless."""
        return not _close(self.actual_answer, self.predicted_under_misconception)


# Phrases that would make an artefact a LECTURE rather than a posed question.
# A counterexample must contain none of these — it surfaces the contradiction,
# it does not state the correction.
_LECTURE_MARKERS: tuple[str, ...] = (
    "the correct rule is",
    "actually, the rule",
    "you should",
    "remember that",
    "the right way",
    "in fact, ",
    "the mistake is",
    "this is wrong because",
    "the answer is",
)


def assert_not_a_lecture(text: str) -> None:
    """Raise if ``text`` reads as a correction/lecture rather than a posed
    question. The load-bearing guard for d12: we detonate by posing, never by
    telling."""
    low = text.lower()
    for marker in _LECTURE_MARKERS:
        if marker in low:
            raise ValueError(
                f"counterexample copy reads as a lecture (matched {marker!r}); "
                "it must pose a question that surfaces the contradiction, not "
                "state the correction."
            )
    if "?" not in text:
        raise ValueError("a posed counterexample must ask a question (no '?').")


def _round_clean(x: float) -> float:
    return round(x, 6)


def engineer_counterexample(
    hypothesis: MisconceptionHypothesis,
    attempt: WrongAttempt,
) -> Counterexample | None:
    """Engineer a counterexample tuned to the proposed misconception.

    Returns None for an UNCLASSIFIED hypothesis — we will not pose a
    counterexample we cannot aim. Each branch builds a fresh item on which the
    wrong rule predicts a checkably-wrong value, and frames it as a question.
    """
    kind = hypothesis.kind

    if kind is MisconceptionKind.FRACTION_ADD_ACROSS:
        # 1/2 + 1/2 = 1, but add-across gives 2/4 = 0.5. A clean split.
        actual = 1.0
        predicted = (1 + 1) / (2 + 2)  # 0.5
        prompt = (
            "Try this one and compare it to your last answer: 1/2 + 1/2. "
            "Half a pizza plus another half — how much pizza is that?"
        )
        follow = (
            "If you add the tops together and the bottoms together, what do you "
            "get, and does that match the pizza?"
        )
        check = {"expression": "1/2 + 1/2", "claimed_answer": actual}
        rationale = (
            "Halves sum to a whole, which add-across cannot reach, so the wrong "
            "rule visibly under-counts on a case the learner can picture."
        )

    elif kind is MisconceptionKind.MULT_ALWAYS_INCREASES:
        # 8 * 0.5 = 4 (smaller than 8). Wrong rule expects >= 8.
        actual = 4.0
        predicted = 8.0
        prompt = (
            "Work this out: 8 * 0.5. Then check it against half of 8 — are they "
            "the same number?"
        )
        follow = (
            "Did multiplying make the number bigger or smaller this time, and "
            "why might that be?"
        )
        check = {"expression": "8 * 0.5", "claimed_answer": actual}
        rationale = (
            "A factor of one-half forces the product below the original, "
            "contradicting the 'multiplication always increases' rule on a case "
            "the learner can verify by halving."
        )

    elif kind is MisconceptionKind.LONGER_DECIMAL_IS_LARGER:
        # Compare 0.5 and 0.45 by lining up on a number line.
        actual = 0.5
        predicted = 0.45
        prompt = (
            "Which is closer to 1: 0.5 or 0.45? Place both on a line from 0 to 1 "
            "and see which one lands further right."
        )
        follow = (
            "0.45 has more digits than 0.5 — does having more digits put it "
            "further along the line?"
        )
        check = {"expression": "0.5 - 0.45", "claimed_answer": _round_clean(0.5 - 0.45)}
        rationale = (
            "On the number line 0.5 sits to the right of 0.45 despite fewer "
            "digits, so the digit-count rule is contradicted spatially."
        )
        # For this kind the 'answer' is the larger value; reframe the check as a
        # difference whose sign settles which is larger.
        return _finalize(kind, prompt, "0.5 vs 0.45", actual, predicted, follow, check, rationale)

    elif kind is MisconceptionKind.SIGN_OR_ORDER_ERROR:
        # 3 - 8 = -5, reversed gives 5. Sign flips.
        actual = -5.0
        predicted = 5.0
        prompt = (
            "Compute 3 - 8 on a number line: start at 3 and move 8 to the left. "
            "Where do you land?"
        )
        follow = (
            "Is landing to the left of zero a positive or a negative number, and "
            "does swapping the two numbers change where you land?"
        )
        check = {"expression": "3 - 8", "claimed_answer": actual}
        rationale = (
            "Starting above zero and stepping past it forces a negative result, "
            "which the order-swap rule cannot produce."
        )

    elif kind is MisconceptionKind.FAULTY_DISTRIBUTION:
        # (1+2)^2 = 9, but 1^2 + 2^2 = 5.
        actual = 9.0
        predicted = 1 * 1 + 2 * 2  # 5
        prompt = (
            "Work out (1 + 2) first, then square it. What do you get? Now compare "
            "that to squaring the 1 and the 2 on their own and adding them."
        )
        follow = (
            "Do the two routes give the same number, and if not, which one "
            "matches counting the squares in a 3-by-3 grid?"
        )
        check = {"expression": "(1 + 2) ** 2", "claimed_answer": actual}
        rationale = (
            "A 3-by-3 grid has nine cells, which term-by-term squaring under-counts "
            "to five, exposing the missing cross term concretely."
        )

    else:  # UNCLASSIFIED — we will not aim a counterexample we cannot target.
        return None

    return _finalize(
        kind, prompt, check["expression"], actual, predicted, follow, check, rationale  # type: ignore[arg-type]
    )


def _finalize(
    kind: MisconceptionKind,
    prompt: str,
    counter_stimulus: str,
    actual: float,
    predicted: float,
    follow: str,
    check: dict[str, object],
    rationale: str,
) -> Counterexample:
    # Enforce the d12 contract before returning: it must POSE, not lecture, and
    # the wrong rule and truth must actually disagree on this item.
    assert_not_a_lecture(prompt)
    assert_not_a_lecture(follow)
    ce = Counterexample(
        misconception=kind,
        prompt=prompt,
        counter_stimulus=counter_stimulus,
        actual_answer=_round_clean(actual),
        predicted_under_misconception=_round_clean(predicted),
        follow_up_question=follow,
        deterministic_check=check,
        rationale=rationale,
    )
    if not ce.surfaces_contradiction:
        raise ValueError(
            "engineered counterexample does not split the wrong rule from the "
            "truth; it would not surface a contradiction."
        )
    return ce


# ---------------------------------------------------------------------------
# The detonation: identify + engineer in one explainable result.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Detonation:
    """The full d12 result for one wrong attempt: a proposed misconception and,
    when it can be aimed, an engineered counterexample posed to the learner.

    Explainable by construction (principle 2): carries the hypothesis, its
    evidence and confidence, the counterexample, and a plain why. Never a
    permanent judgment (``hypothesis.confirmed`` is False from one attempt)."""

    topic_id: str
    hypothesis: MisconceptionHypothesis
    counterexample: Counterexample | None
    served: bool                       # True only when a posable counterexample exists
    explanation: str                   # plain, learner-neutral why-this-move

    @property
    def is_lecture_free(self) -> bool:
        """True when the served artefact poses rather than lectures. A safety
        property the surface can assert before showing anything."""
        if self.counterexample is None:
            return True
        try:
            assert_not_a_lecture(self.counterexample.prompt)
            assert_not_a_lecture(self.counterexample.follow_up_question)
            return True
        except ValueError:
            return False


def _coerce_attempt(attempt: object) -> WrongAttempt:
    """Accept a WrongAttempt, a mapping, or any object carrying the public attempt
    fields, and normalise to a WrongAttempt. The surface speaks
    prompt/answer/expected/concept_id; this maps them to the internal
    stimulus/learner_answer/correct_answer/topic_id without inventing values."""
    if isinstance(attempt, WrongAttempt):
        return attempt
    if isinstance(attempt, dict):
        d = attempt
    else:
        d = {
            k: getattr(attempt, k)
            for k in (
                "topic_id", "concept_id", "stimulus", "prompt", "learner_answer",
                "answer", "correct_answer", "expected", "operands", "operator",
                "question_id",
            )
            if hasattr(attempt, k)
        }
    topic = d.get("topic_id") or d.get("concept_id") or ""
    stimulus = str(d.get("stimulus") or d.get("prompt") or "")
    learner = d.get("learner_answer", d.get("answer"))
    correct = d.get("correct_answer", d.get("expected"))
    operands = tuple(d.get("operands") or ())
    operator = d.get("operator")
    # When the surface did not pre-parse the item, infer operands/operator from a
    # simple binary stimulus like "3 - 5" so the deterministic detectors can run.
    if not operands or operator is None:
        parsed = _parse_binary(stimulus)
        if parsed is not None:
            operands, operator = parsed
    return WrongAttempt(
        topic_id=str(topic),
        stimulus=stimulus,
        learner_answer="" if learner is None else str(learner),
        correct_answer="" if correct is None else str(correct),
        operands=operands,
        operator=operator,
        question_id=d.get("question_id"),
    )


def _parse_binary(stimulus: str) -> tuple[tuple[float, float], str] | None:
    """Parse a simple 'a op b' expression (e.g. '3 - 5', '1/2 + 1/4') into
    structured operands + operator. Returns None when the stimulus is not a
    plain binary expression."""
    m = re.fullmatch(
        r"\s*(-?\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)\s*([+\-*x/])\s*"
        r"(-?\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)\s*",
        stimulus,
    )
    if not m:
        return None
    a, b = _to_number(m.group(1)), _to_number(m.group(3))
    if a is None or b is None:
        return None
    op = "*" if m.group(2) == "x" else m.group(2)
    return (a, b), op


def detonate(
    attempt: WrongAttempt | dict,
    *,
    detectors: Sequence[Detector] = DEFAULT_DETECTORS,
) -> Detonation:
    """The d12 entrypoint: from a wrong answer, identify the likely misconception
    and engineer a counterexample that surfaces the contradiction.

    Accepts a WrongAttempt or the surface's attempt mapping (prompt/answer/
    expected/concept_id). A CORRECT attempt is declined (``served`` False) rather
    than raising — there is simply nothing to detonate. Degrades safely: when the
    misconception cannot be classified or aimed, no counterexample is posed and
    the explanation says to gather another attempt rather than guessing — a single
    interaction never becomes a permanent judgment.
    """
    attempt = _coerce_attempt(attempt)

    # A correct attempt has nothing to detonate. Decline calmly; never raise.
    lv, cv = attempt.learner_value, attempt.correct_value
    if lv is not None and cv is not None and _close(lv, cv):
        return Detonation(
            topic_id=attempt.topic_id,
            hypothesis=MisconceptionHypothesis(
                kind=MisconceptionKind.UNCLASSIFIED,
                confidence=0.0,
                evidence="The attempt is correct; there is nothing to detonate.",
                predicted_wrong_answer=None,
            ),
            counterexample=None,
            served=False,
            explanation="This attempt is correct; there is no misconception to surface.",
        )

    hypothesis = identify_misconception(attempt, detectors=detectors)
    counterexample = engineer_counterexample(hypothesis, attempt)

    if counterexample is None:
        explanation = (
            "This answer is wrong, but one attempt does not pin down the wrong "
            "rule behind it. Pose another item on the same idea before drawing a "
            "conclusion — no judgment from a single interaction."
        )
        return Detonation(
            topic_id=attempt.topic_id,
            hypothesis=hypothesis,
            counterexample=None,
            served=False,
            explanation=explanation,
        )

    explanation = (
        f"Likely misconception (proposed, not confirmed): "
        f"{KIND_DESCRIPTION[hypothesis.kind]} {hypothesis.evidence} "
        f"The next item is engineered so the same wrong rule would give "
        f"{counterexample.predicted_under_misconception:g} while the true answer "
        f"is {counterexample.actual_answer:g} — the learner is asked to work it "
        f"out and see the gap, not told the correction."
    )
    return Detonation(
        topic_id=attempt.topic_id,
        hypothesis=hypothesis,
        counterexample=counterexample,
        served=True,
        explanation=explanation,
    )
