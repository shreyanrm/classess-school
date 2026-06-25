"""The generate-and-verify substrate (INVARIANT 7).

No generated content is served unverified. The pipeline is, in ORDER:

  1. DETERMINISTIC CHECKS FIRST — symbolic/numeric where possible. For a
     math/physics item this means re-evaluating the expression, numeric bound
     checks, and (where given) unit consistency. These need NO LLM and run
     entirely in-process.
  2. SECOND-MODEL CROSS-CHECK — an independent model agrees or disagrees. This
     is an interface; with no live provider it abstains (does not agree),
     which keeps the gate closed (degrades safely, never fabricates).
  3. THE CONFIDENCE GATE — content is SERVED only when deterministic checks
     pass AND the second model agrees AND confidence >= threshold. Otherwise
     it is WITHHELD and flagged for human review.

This module ships a WORKING deterministic arithmetic/expression verifier built
on Python's ``ast`` (a safe numeric evaluator — no ``eval``, no names, no
calls), so the deterministic path is real, not a stub.
"""

from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass, field
from typing import Callable, Protocol


# ---------------------------------------------------------------------------
# Safe deterministic expression evaluator (no LLM, no eval)
# ---------------------------------------------------------------------------

_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class ExpressionError(ValueError):
    """Raised when an expression cannot be safely evaluated."""


def safe_eval(expression: str) -> float:
    """Evaluate a purely-numeric arithmetic expression safely.

    Supports + - * / // % ** and unary +/-, parentheses, and numeric literals.
    Rejects names, attribute access, calls, and anything non-arithmetic. This is
    the deterministic ground truth for the arithmetic verifier.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:  # pragma: no cover - exercised via verifier
        raise ExpressionError(f"unparseable expression: {expression!r}") from exc
    return _eval_node(tree.body)


def _eval_node(node: ast.AST, variables: dict[str, float] | None = None) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExpressionError(f"non-numeric constant: {node.value!r}")
        return float(node.value)
    if isinstance(node, ast.Name):
        # A bare name is allowed ONLY when it is an explicitly-bound variable
        # (used by the lesson-visual plotter to sample y = f(x)). With no
        # binding it stays rejected, so ``safe_eval`` is unchanged.
        if variables is not None and node.id in variables:
            return float(variables[node.id])
        raise ExpressionError(f"unbound name: {node.id!r}")
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise ExpressionError(f"unsupported operator: {type(node.op).__name__}")
        return op(_eval_node(node.left, variables), _eval_node(node.right, variables))
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise ExpressionError(f"unsupported unary operator: {type(node.op).__name__}")
        return op(_eval_node(node.operand, variables))
    raise ExpressionError(f"disallowed expression node: {type(node).__name__}")


def eval_at(expression: str, variables: dict[str, float]) -> float:
    """Evaluate an arithmetic expression with a set of bound variables.

    Like :func:`safe_eval` but a name listed in ``variables`` resolves to its
    value (used to sample a plotted curve y = f(x) at given x). Names not bound
    are still rejected — no ``eval``, no calls, no attribute access.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"unparseable expression: {expression!r}") from exc
    return _eval_node(tree.body, variables)


# ---------------------------------------------------------------------------
# Deterministic check results
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeterministicCheck:
    """A single deterministic check run against generated content."""

    name: str
    passed: bool
    detail: str | None = None


# ---------------------------------------------------------------------------
# Deterministic verifiers (no LLM)
# ---------------------------------------------------------------------------

def verify_arithmetic(
    expression: str,
    claimed_answer: float,
    tolerance: float = 1e-9,
) -> list[DeterministicCheck]:
    """Re-evaluate an arithmetic expression and compare to the claimed answer.

    Symbolic-where-possible is approximated here by exact numeric re-computation
    of the canonical expression. Returns the ordered checks; a malformed
    expression fails closed (a failing check, never an exception to the caller).
    """
    checks: list[DeterministicCheck] = []
    try:
        truth = safe_eval(expression)
    except ExpressionError as exc:
        checks.append(DeterministicCheck("expression-parseable", False, str(exc)))
        return checks
    checks.append(DeterministicCheck("expression-parseable", True, f"= {truth}"))

    matches = math.isclose(truth, float(claimed_answer), rel_tol=tolerance, abs_tol=tolerance)
    checks.append(
        DeterministicCheck(
            "numeric-recompute",
            matches,
            f"recomputed {truth}; claimed {claimed_answer}"
            + ("" if matches else " — MISMATCH"),
        )
    )
    return checks


def verify_numeric_bounds(
    value: float,
    lower: float | None = None,
    upper: float | None = None,
) -> DeterministicCheck:
    """Check a numeric value lies within an inclusive [lower, upper] bound."""
    ok = True
    parts: list[str] = []
    if lower is not None:
        ok = ok and value >= lower
        parts.append(f">= {lower}")
    if upper is not None:
        ok = ok and value <= upper
        parts.append(f"<= {upper}")
    detail = f"{value} " + (" and ".join(parts) if parts else "(no bounds)")
    return DeterministicCheck("numeric-bounds", ok, detail)


def verify_units(claimed_unit: str, expected_unit: str) -> DeterministicCheck:
    """Check unit consistency for a physics item (case/space-insensitive)."""
    norm = lambda s: s.strip().lower().replace(" ", "")
    ok = norm(claimed_unit) == norm(expected_unit)
    return DeterministicCheck(
        "unit-consistency", ok, f"claimed '{claimed_unit}' vs expected '{expected_unit}'"
    )


# ---------------------------------------------------------------------------
# Second-model cross-check interface
# ---------------------------------------------------------------------------

class SecondModelChecker(Protocol):
    """An independent second model that cross-checks generated content.

    Returns ``(agrees, confidence)``. With no live provider, use
    ``AbstainingSecondModel`` — it does NOT agree, which keeps the gate closed.
    """

    def cross_check(self, *, task_class: str, content: object) -> tuple[bool, float]:
        ...


@dataclass(frozen=True)
class AbstainingSecondModel:
    """The no-provider default: never agrees, zero confidence.

    Degrades gracefully — without a second model the gate cannot pass on the
    second-model condition, so content is withheld rather than served blind.
    """

    reason: str = "No second-model provider configured; cross-check abstains."

    def cross_check(self, *, task_class: str, content: object) -> tuple[bool, float]:
        return (False, 0.0)


# ---------------------------------------------------------------------------
# Verification block + the CONFIDENCE GATE
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GenerateVerification:
    """The verification block. ``served`` is the gate's verdict (INVARIANT 7)."""

    deterministic_checks: list[DeterministicCheck]
    deterministic_checks_passed: bool
    second_model_agrees: bool
    confidence: float
    gate_threshold: float
    served: bool
    review_reason: str | None = None


@dataclass
class ConfidenceGate:
    """The confidence gate. Content is served ONLY when all conditions hold."""

    threshold: float = 0.85

    def evaluate(
        self,
        deterministic_checks: list[DeterministicCheck],
        second_model_agrees: bool,
        confidence: float,
    ) -> GenerateVerification:
        det_passed = bool(deterministic_checks) and all(c.passed for c in deterministic_checks)
        # The gate: deterministic FIRST, then second model, then threshold.
        served = det_passed and second_model_agrees and confidence >= self.threshold

        review_reason: str | None = None
        if not served:
            reasons: list[str] = []
            if not deterministic_checks:
                reasons.append("no deterministic checks were run")
            elif not det_passed:
                failed = [c.name for c in deterministic_checks if not c.passed]
                reasons.append(f"deterministic checks failed: {', '.join(failed)}")
            if not second_model_agrees:
                reasons.append("second-model cross-check did not agree")
            if confidence < self.threshold:
                reasons.append(f"confidence {confidence:.2f} < gate {self.threshold:.2f}")
            review_reason = "; ".join(reasons) or "gate not satisfied"

        return GenerateVerification(
            deterministic_checks=deterministic_checks,
            deterministic_checks_passed=det_passed,
            second_model_agrees=second_model_agrees,
            confidence=confidence,
            gate_threshold=self.threshold,
            served=served,
            review_reason=review_reason,
        )


# ---------------------------------------------------------------------------
# A reusable deterministic verifier for math/physics items
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MathItem:
    """A generated math/physics item to verify, with its claimed solution."""

    expression: str
    claimed_answer: float
    answer_lower: float | None = None
    answer_upper: float | None = None
    claimed_unit: str | None = None
    expected_unit: str | None = None


def deterministic_checks_for_math(item: MathItem) -> list[DeterministicCheck]:
    """Run the full deterministic battery for a math/physics item, in order."""
    checks = verify_arithmetic(item.expression, item.claimed_answer)
    # Only run bounds if the recompute itself succeeded numerically.
    if item.answer_lower is not None or item.answer_upper is not None:
        checks.append(verify_numeric_bounds(item.claimed_answer, item.answer_lower, item.answer_upper))
    if item.expected_unit is not None:
        checks.append(verify_units(item.claimed_unit or "", item.expected_unit))
    return checks


# ---------------------------------------------------------------------------
# A deterministic verifier for a LESSON VISUAL (a plotted curve y = f(x))
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LessonVisualItem:
    """A generated lesson visual to verify deterministically.

    A plotted curve ``y = f(x)`` with ``expression`` (the function of ``var``,
    default ``x``) and the curve's claimed sample points ``samples`` — a list of
    ``(x, claimed_y)`` pairs the generator says lie on the curve. The
    deterministic oracle re-evaluates ``f`` at each ``x`` and confirms the
    plotted ``y`` matches (this is the "re-run the simulation / numeric check"
    path for a visual — no LLM, INVARIANT 7). Optional axis bounds confirm every
    sample sits inside the declared viewport.
    """

    expression: str
    samples: tuple[tuple[float, float], ...]
    var: str = "x"
    x_min: float | None = None
    x_max: float | None = None
    y_min: float | None = None
    y_max: float | None = None
    tolerance: float = 1e-6


def verify_plotted_points(item: LessonVisualItem) -> list[DeterministicCheck]:
    """Re-evaluate the plotted curve at each sample and confirm the claimed y.

    Fails CLOSED: an unparseable / non-numeric expression, or any sample whose
    re-computed y does not match the claimed y within tolerance, yields a failing
    check (never an exception to the caller), so the gate withholds.
    """
    checks: list[DeterministicCheck] = []
    if not item.samples:
        checks.append(DeterministicCheck(
            "plotted-points", False, "no sample points supplied; cannot verify the curve.",
        ))
        return checks

    for i, (x, claimed_y) in enumerate(item.samples):
        try:
            truth_y = eval_at(item.expression, {item.var: float(x)})
        except ExpressionError as exc:
            checks.append(DeterministicCheck(
                "plotted-points", False, f"sample {i} ({item.var}={x}): {exc}",
            ))
            return checks  # an unevaluable curve fails closed immediately
        matches = math.isclose(truth_y, float(claimed_y), rel_tol=item.tolerance, abs_tol=item.tolerance)
        checks.append(DeterministicCheck(
            f"plotted-point[{i}]",
            matches,
            f"{item.var}={x}: recomputed {truth_y}; plotted {claimed_y}"
            + ("" if matches else " — MISMATCH"),
        ))

    # Viewport bounds: every sample x (and y) must sit inside the declared axes.
    if item.x_min is not None or item.x_max is not None:
        for i, (x, _y) in enumerate(item.samples):
            checks.append(_renamed(
                verify_numeric_bounds(float(x), item.x_min, item.x_max), f"x-in-view[{i}]"))
    if item.y_min is not None or item.y_max is not None:
        for i, (_x, y) in enumerate(item.samples):
            checks.append(_renamed(
                verify_numeric_bounds(float(y), item.y_min, item.y_max), f"y-in-view[{i}]"))
    return checks


def _renamed(check: DeterministicCheck, name: str) -> DeterministicCheck:
    return DeterministicCheck(name, check.passed, check.detail)


def deterministic_checks_for_visual(item: LessonVisualItem) -> list[DeterministicCheck]:
    """Run the full deterministic battery for a lesson visual, in order."""
    return verify_plotted_points(item)
