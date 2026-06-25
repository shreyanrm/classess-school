"""Tests for the deterministic verifier and the confidence gate.

Import-safe, no network.
"""

from __future__ import annotations

import pytest

from app.verify import (
    ConfidenceGate,
    DeterministicCheck,
    ExpressionError,
    LessonVisualItem,
    MathItem,
    deterministic_checks_for_math,
    deterministic_checks_for_visual,
    eval_at,
    safe_eval,
    verify_arithmetic,
    verify_numeric_bounds,
    verify_plotted_points,
    verify_units,
)


# -- the safe evaluator ----------------------------------------------------

@pytest.mark.parametrize("expr,expected", [
    ("2 + 2", 4.0),
    ("3 * (4 + 5)", 27.0),
    ("2 ** 10", 1024.0),
    ("10 / 4", 2.5),
    ("-7 + 3", -4.0),
    ("17 % 5", 2.0),
])
def test_safe_eval_arithmetic(expr, expected):
    assert safe_eval(expr) == expected


@pytest.mark.parametrize("expr", [
    "__import__('os')",   # no calls
    "os.system",          # no attribute access
    "x + 1",              # no names
    "2 +",                # unparseable
])
def test_safe_eval_rejects_unsafe(expr):
    with pytest.raises(ExpressionError):
        safe_eval(expr)


# -- arithmetic verifier ---------------------------------------------------

def test_verify_arithmetic_correct():
    checks = verify_arithmetic("12 * 12", 144)
    assert all(c.passed for c in checks)
    assert any(c.name == "numeric-recompute" and c.passed for c in checks)


def test_verify_arithmetic_wrong_answer():
    checks = verify_arithmetic("12 * 12", 140)
    recompute = [c for c in checks if c.name == "numeric-recompute"][0]
    assert recompute.passed is False
    assert "MISMATCH" in (recompute.detail or "")


def test_verify_arithmetic_malformed_fails_closed():
    checks = verify_arithmetic("12 *", 0)
    # Fails closed: a failing parse check, no exception leaks.
    assert checks[0].name == "expression-parseable"
    assert checks[0].passed is False


def test_verify_numeric_bounds():
    assert verify_numeric_bounds(5, lower=0, upper=10).passed is True
    assert verify_numeric_bounds(11, lower=0, upper=10).passed is False
    assert verify_numeric_bounds(-1, lower=0).passed is False


def test_verify_units():
    assert verify_units("m/s", "m / s").passed is True
    assert verify_units("kg", "m").passed is False


def test_deterministic_checks_for_math_full_battery():
    item = MathItem(
        expression="9.8 * 2",
        claimed_answer=19.6,
        answer_lower=0,
        answer_upper=100,
        claimed_unit="m/s",
        expected_unit="m/s",
    )
    checks = deterministic_checks_for_math(item)
    assert all(c.passed for c in checks)
    names = {c.name for c in checks}
    assert {"numeric-recompute", "numeric-bounds", "unit-consistency"} <= names


# -- the confidence gate ---------------------------------------------------

def _ok_checks():
    return [DeterministicCheck("numeric-recompute", True, "ok")]


def test_gate_serves_when_all_pass():
    gate = ConfidenceGate(threshold=0.85)
    v = gate.evaluate(_ok_checks(), second_model_agrees=True, confidence=0.9)
    assert v.served is True
    assert v.review_reason is None


def test_gate_withholds_on_failed_deterministic():
    gate = ConfidenceGate(threshold=0.85)
    failed = [DeterministicCheck("numeric-recompute", False, "mismatch")]
    v = gate.evaluate(failed, second_model_agrees=True, confidence=0.99)
    assert v.served is False
    assert "deterministic checks failed" in (v.review_reason or "")


def test_gate_withholds_when_second_model_disagrees():
    gate = ConfidenceGate(threshold=0.85)
    v = gate.evaluate(_ok_checks(), second_model_agrees=False, confidence=0.99)
    assert v.served is False
    assert "second-model" in (v.review_reason or "")


def test_gate_withholds_below_threshold():
    gate = ConfidenceGate(threshold=0.85)
    v = gate.evaluate(_ok_checks(), second_model_agrees=True, confidence=0.5)
    assert v.served is False
    assert "confidence" in (v.review_reason or "")


def test_gate_withholds_with_no_checks():
    gate = ConfidenceGate(threshold=0.85)
    v = gate.evaluate([], second_model_agrees=True, confidence=0.99)
    assert v.served is False
    assert v.deterministic_checks_passed is False


# -- lesson-visual deterministic verifier (plotted curve y = f(x)) ---------

def test_eval_at_binds_variable_but_safe_eval_still_rejects_names():
    assert eval_at("x ** 2", {"x": 3}) == 9.0
    assert eval_at("2 * t + 1", {"t": 4}) == 9.0
    # safe_eval (no binding) is UNCHANGED: a bare name is still rejected.
    with pytest.raises(ExpressionError):
        safe_eval("x + 1")
    # An unbound name under eval_at is also rejected (no silent zero).
    with pytest.raises(ExpressionError):
        eval_at("y + 1", {"x": 2})


def test_visual_correct_plotted_points_pass():
    item = LessonVisualItem(
        expression="x ** 2",
        samples=((-2, 4), (0, 0), (3, 9)),
        x_min=-5, x_max=5, y_min=0, y_max=25,
    )
    checks = deterministic_checks_for_visual(item)
    assert all(c.passed for c in checks)
    assert any(c.name.startswith("plotted-point") for c in checks)
    assert any(c.name.startswith("x-in-view") for c in checks)


def test_visual_wrong_plotted_point_fails_closed():
    item = LessonVisualItem(expression="x ** 2", samples=((2, 5),))  # 2**2 = 4, not 5
    checks = verify_plotted_points(item)
    assert any(c.name.startswith("plotted-point") and not c.passed for c in checks)


def test_visual_unevaluable_curve_fails_closed():
    item = LessonVisualItem(expression="sin(x)", samples=((0, 0),))  # no calls allowed
    checks = verify_plotted_points(item)
    assert checks[0].name == "plotted-points"
    assert checks[0].passed is False


def test_visual_no_samples_fails_closed():
    checks = verify_plotted_points(LessonVisualItem(expression="x", samples=()))
    assert checks[0].passed is False


def test_visual_sample_outside_viewport_fails():
    item = LessonVisualItem(expression="x ** 2", samples=((10, 100),), y_min=0, y_max=25)
    checks = deterministic_checks_for_visual(item)
    # The point is on the curve (10**2 == 100) but outside the declared y view.
    assert any(c.name.startswith("plotted-point") and c.passed for c in checks)
    assert any(c.name.startswith("y-in-view") and not c.passed for c in checks)
