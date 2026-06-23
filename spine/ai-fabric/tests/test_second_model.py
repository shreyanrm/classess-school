"""Tests for the LIVE second-model cross-checker and the live-vs-abstain factory.

INVARIANT 7 — the confidence gate serves content ONLY when an independent second
model agrees. These tests prove:

  - a stub provider that AGREES lets the gate pass (with deterministic checks ok),
  - a stub provider that REFUSES keeps the gate closed,
  - with NO key the factory falls back to abstaining (gate stays closed),
  - the raw key NEVER appears in any returned result or verdict.

Import-safe, no network.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.config import get_settings
from app.second_model import (
    CROSSCHECK_KEY_ENV_VAR,
    CrossCheckVerdict,
    LiveSecondModel,
    make_second_model,
)
from app.verify import AbstainingSecondModel, ConfidenceGate, DeterministicCheck

# A sentinel raw key value used across tests; it must never leak into results.
SECRET_KEY_VALUE = "super-secret-crosscheck-key-DO-NOT-LEAK"


# ---------------------------------------------------------------------------
# Stub providers (the seam) — never the real network
# ---------------------------------------------------------------------------

@dataclass
class AgreeingProvider:
    """A stub cross-check provider that confirms content. Records the raw key it
    was handed so a test can assert the key reaches the seam but no further."""

    confidence: float = 0.95
    seen_key: str | None = None

    def cross_check(self, *, raw_key, model_label, task_class, content) -> CrossCheckVerdict:
        self.seen_key = raw_key
        return CrossCheckVerdict(agrees=True, confidence=self.confidence)


@dataclass
class RefusingProvider:
    """A stub cross-check provider that refutes content."""

    seen_key: str | None = None

    def cross_check(self, *, raw_key, model_label, task_class, content) -> CrossCheckVerdict:
        self.seen_key = raw_key
        return CrossCheckVerdict(agrees=False, confidence=0.9)


@dataclass
class ExplodingProvider:
    """A stub provider that errors — the live model must fail closed."""

    def cross_check(self, *, raw_key, model_label, task_class, content) -> CrossCheckVerdict:
        raise RuntimeError("provider blew up")


def _settings_with_key(value: str = SECRET_KEY_VALUE):
    return get_settings({CROSSCHECK_KEY_ENV_VAR: value})


def _settings_without_key():
    return get_settings({})


def _ok_checks():
    return [DeterministicCheck("numeric-recompute", True, "ok")]


# ---------------------------------------------------------------------------
# Factory: live vs abstain by config
# ---------------------------------------------------------------------------

def test_factory_returns_live_when_key_and_provider_present():
    sm = make_second_model(settings=_settings_with_key(), provider=AgreeingProvider())
    assert isinstance(sm, LiveSecondModel)


def test_factory_abstains_with_no_key():
    sm = make_second_model(settings=_settings_without_key(), provider=AgreeingProvider())
    assert isinstance(sm, AbstainingSecondModel)


def test_factory_abstains_with_key_but_no_provider():
    # Key present but no provider seam wired => fall back to abstaining.
    sm = make_second_model(settings=_settings_with_key(), provider=None)
    assert isinstance(sm, AbstainingSecondModel)


def test_factory_picks_abstain_from_empty_env():
    sm = make_second_model(env={}, provider=AgreeingProvider())
    assert isinstance(sm, AbstainingSecondModel)


# ---------------------------------------------------------------------------
# Cross-check behaviour
# ---------------------------------------------------------------------------

def test_agreeing_provider_lets_gate_pass():
    sm = LiveSecondModel(provider=AgreeingProvider(confidence=0.95), settings=_settings_with_key())
    agrees, conf = sm.cross_check(task_class="content.generate-practice-item", content="2+2=4")
    assert agrees is True
    assert conf == pytest.approx(0.95)

    gate = ConfidenceGate(threshold=0.85)
    verdict = gate.evaluate(_ok_checks(), second_model_agrees=agrees, confidence=conf)
    assert verdict.served is True


def test_refusing_provider_keeps_gate_closed():
    sm = LiveSecondModel(provider=RefusingProvider(), settings=_settings_with_key())
    agrees, conf = sm.cross_check(task_class="content.generate-practice-item", content="2+2=5")
    assert agrees is False
    assert conf == 0.0

    gate = ConfidenceGate(threshold=0.85)
    verdict = gate.evaluate(_ok_checks(), second_model_agrees=agrees, confidence=conf)
    assert verdict.served is False
    assert "second-model" in (verdict.review_reason or "")


def test_no_key_abstains_and_gate_closed():
    sm = LiveSecondModel(provider=AgreeingProvider(), settings=_settings_without_key())
    assert sm.has_provider() is False
    agrees, conf = sm.cross_check(task_class="content.generate-practice-item", content="x")
    assert agrees is False
    assert conf == 0.0

    gate = ConfidenceGate(threshold=0.85)
    verdict = gate.evaluate(_ok_checks(), second_model_agrees=agrees, confidence=conf)
    assert verdict.served is False


def test_provider_error_fails_closed():
    sm = LiveSecondModel(provider=ExplodingProvider(), settings=_settings_with_key())
    agrees, conf = sm.cross_check(task_class="content.generate-practice-item", content="x")
    assert agrees is False
    assert conf == 0.0


def test_out_of_range_confidence_is_clamped():
    sm = LiveSecondModel(provider=AgreeingProvider(confidence=5.0), settings=_settings_with_key())
    agrees, conf = sm.cross_check(task_class="x", content="y")
    assert agrees is True
    assert conf == 1.0


# ---------------------------------------------------------------------------
# The raw key never leaks
# ---------------------------------------------------------------------------

def test_raw_key_never_in_cross_check_result():
    provider = AgreeingProvider()
    sm = LiveSecondModel(provider=provider, settings=_settings_with_key())
    result = sm.cross_check(task_class="x", content="content")
    # The seam was handed the key (it is the only place it may go) ...
    assert provider.seen_key == SECRET_KEY_VALUE
    # ... but the returned tuple is only (agrees, confidence) — no key.
    assert SECRET_KEY_VALUE not in repr(result)
    for part in result:
        assert SECRET_KEY_VALUE != part
        assert SECRET_KEY_VALUE not in repr(part)


def test_raw_key_not_in_repr_of_live_model_attrs():
    sm = LiveSecondModel(provider=AgreeingProvider(), settings=_settings_with_key())
    # The model never stores the key as a public/derived attribute; it reads it
    # transiently. Its repr (and the factory's chosen object) must not expose it.
    chosen = make_second_model(settings=_settings_with_key(), provider=AgreeingProvider())
    assert SECRET_KEY_VALUE not in repr(chosen)
    # _raw_key is private and returns the value for the seam only.
    assert sm._raw_key() == SECRET_KEY_VALUE
