"""Behavioral contract tests for learning.misconception (d12 detonation).

Asserts the d12 contract from the laws dossier: from a wrong answer the module
identifies the likely misconception and produces a targeted COUNTEREXAMPLE that
surfaces the contradiction -- it POSES a probe, it does not lecture.

This suite is written to the *behavioral* contract and adapts to the module's
public entry point (so it is resilient to naming), rather than to private
internals. It runs with no network, DB, or live keys.
"""

from __future__ import annotations

import inspect
import os
import sys

import pytest

_MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _MODULE_DIR not in sys.path:
    sys.path.insert(0, _MODULE_DIR)

misconception = pytest.importorskip(
    "misconception",
    reason="learning.misconception module not importable in this environment",
)


# Phrasings that would make a probe a lecture rather than a posed challenge.
LECTURE_MARKERS = (
    "you are wrong",
    "you're wrong",
    "the correct answer is",
    "remember that",
    "the rule is",
    "you should",
    "you made a mistake",
    "incorrect because",
    "let me explain",
)


def _entry_point():
    """Find the public detonation entry point on the module."""

    for name in ("detonate", "detect_and_counter", "detonation", "analyze",
                 "analyse", "run", "process_attempt"):
        fn = getattr(misconception, name, None)
        if callable(fn):
            return fn
    pytest.skip("no recognised misconception entry point found")


def _make_attempt(**over):
    """Build an attempt input compatible with the module's Attempt type.

    Falls back to a plain dict if no Attempt dataclass is exported.
    """

    base = dict(
        canonical_uuid="123e4567-e89b-12d3-a456-426614174000",
        concept_id="math.subtraction",
        prompt="3 - 5",
        answer="2",
        expected="-2",
        is_correct=False,
    )
    base.update(over)
    Attempt = getattr(misconception, "Attempt", None)
    if Attempt is None:
        return base
    # Only pass fields the Attempt type accepts.
    try:
        sig = inspect.signature(Attempt)
        accepted = {k: v for k, v in base.items() if k in sig.parameters}
        return Attempt(**accepted)
    except (TypeError, ValueError):
        return base


def _probe_text(result) -> str:
    """Extract the posed probe text from a result, across shapes."""

    # direct attributes
    for attr in ("counterexample", "probe"):
        obj = getattr(result, attr, None)
        if obj is None:
            continue
        if isinstance(obj, str):
            return obj
        probe = getattr(obj, "probe", None)
        if isinstance(probe, str):
            return probe
    # mapping shape
    if isinstance(result, dict):
        ce = result.get("counterexample") or {}
        if isinstance(ce, dict):
            return str(ce.get("probe", ""))
        return str(result.get("probe", ""))
    return ""


def test_module_import_safe():
    assert misconception is not None


def test_wrong_answer_yields_targeted_counterexample():
    fn = _entry_point()
    result = fn(_make_attempt())
    probe = _probe_text(result)
    assert probe, "a wrong answer should yield a posed counterexample probe"


def test_counterexample_poses_not_lectures():
    fn = _entry_point()
    result = fn(_make_attempt())
    probe = _probe_text(result)
    if not probe:
        pytest.skip("no probe produced to evaluate")
    low = probe.lower()
    # It must POSE: a question, not a statement of the rule.
    assert "?" in probe or any(
        w in low for w in ("how ", "which ", "what ")
    ), "the probe must pose a question"
    # It must NOT lecture.
    for marker in LECTURE_MARKERS:
        assert marker not in low, f"probe lectures via phrase: {marker!r}"


def test_correct_attempt_is_not_detonated():
    fn = _entry_point()
    result = fn(_make_attempt(is_correct=True, answer="-2"))
    probe = _probe_text(result)
    assert not probe, "a correct attempt should not produce a counterexample"


def test_pii_free_reference_enforced():
    """A non-opaque (PII-like) learner reference must be rejected if guarded."""

    guard = getattr(misconception, "assert_pii_free", None)
    if guard is None:
        pytest.skip("module does not expose a PII guard")
    # opaque uuid passes
    guard("123e4567-e89b-12d3-a456-426614174000")
    # an e-mail must be rejected
    with pytest.raises(Exception):
        guard("child@example.com")
