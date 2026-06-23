"""Tests for the Track 2 (proprietary / edge SLM) adapter.

Covers, with NO network and NO DB (import-safe):

  - Track 1 and Track 2 are selected for the RIGHT task classes and never
    conflated (INVARIANT 11);
  - Track 2 degrades gracefully when its endpoint is unset (clearly-marked
    unavailable, never fabricated);
  - the CONFIDENCE GATE still applies to Track 2 output (INVARIANT 7).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.capability_registry import CapabilityRegistry, default_registry
from app.config import get_settings
from app.router import (
    ModelRouter,
    ModelTier,
    RouterSelectionInput,
    Track1Config,
    env_var_name,
)
from app.track2 import (
    EDGE_SLM_HINT_MODEL_LABEL,
    HINT_TASK_CLASS,
    INTENT_TASK_CLASS,
    TRACK2_ENDPOINT_KEY_ENV_VAR,
    TRACK2_ENDPOINT_KEY_SECRET_NAME,
    TRACK2_ENDPOINT_URL_ENV_VAR,
    TRACK_ID,
    EdgeCandidate,
    Track2Adapter,
    Track2Result,
    register_track2_capabilities,
    track2_capabilities,
    track2_config,
)


# ---------------------------------------------------------------------------
# Test seams (no network)
# ---------------------------------------------------------------------------

@dataclass
class _FakeEndpoint:
    """A deterministic edge SLM seam returning a fixed candidate."""

    text: str = "Try isolating x first."
    confidence: float = 0.99
    seen_key: str | None = None

    def infer(self, *, raw_key, endpoint_url, model_label, task_class, prompt):
        self.seen_key = raw_key  # to assert the key reaches the seam, never a result
        return EdgeCandidate(text=self.text, confidence=self.confidence)


@dataclass(frozen=True)
class _AgreeingSecondModel:
    """A second model that agrees with high confidence (for the served path)."""

    confidence: float = 0.99

    def cross_check(self, *, task_class, content):
        return (True, self.confidence)


def _env_with_track2(url="https://edge.invalid", key="present-by-name-only"):
    return {
        TRACK2_ENDPOINT_URL_ENV_VAR: url,
        TRACK2_ENDPOINT_KEY_ENV_VAR: key,
    }


# ---------------------------------------------------------------------------
# Track selection — the right task classes, never conflated (INVARIANT 11)
# ---------------------------------------------------------------------------

def test_edge_task_classes_select_edge_tier():
    r = ModelRouter(env={})
    for tc in (HINT_TASK_CLASS, INTENT_TASK_CLASS):
        sel = r.select_tier(RouterSelectionInput(tc, requires_verification=True, track=TRACK_ID))
        assert sel.tier is ModelTier.EDGE


def test_track2_route_resolves_on_track2_for_edge_task():
    key = env_var_name(TRACK2_ENDPOINT_KEY_SECRET_NAME)
    env = _env_with_track2()
    env[key] = env[TRACK2_ENDPOINT_KEY_ENV_VAR]
    r = ModelRouter(track2=track2_config(), env=env)
    res = r.resolve(RouterSelectionInput(HINT_TASK_CLASS, requires_verification=True, track=TRACK_ID))
    assert res.available is True
    assert res.selection.track == TRACK_ID
    assert res.selection.tier is ModelTier.EDGE
    assert res.model is not None
    assert res.model.model_label == EDGE_SLM_HINT_MODEL_LABEL


def test_track1_and_track2_not_conflated_for_same_task_class():
    # The SAME edge task class resolves on whichever track is requested, never
    # borrowing the other's config.
    t1_key = env_var_name(Track1Config().provider_key_env)
    t2_key = env_var_name(TRACK2_ENDPOINT_KEY_SECRET_NAME)
    env = {t1_key: "t1-present", t2_key: "t2-present", **_env_with_track2()}
    r = ModelRouter(track2=track2_config(), env=env)

    via_t1 = r.resolve(RouterSelectionInput(HINT_TASK_CLASS, requires_verification=True, track=1))
    via_t2 = r.resolve(RouterSelectionInput(HINT_TASK_CLASS, requires_verification=True, track=2))

    assert via_t1.selection.track == 1
    assert via_t2.selection.track == TRACK_ID
    # Distinct provider key env names — the tracks never share a secret.
    assert via_t1.provider_key_env != via_t2.provider_key_env


def test_track2_selection_never_borrows_track1_key():
    # Track 1 has a key; Track 2 does not. A track-2 intent stays unavailable
    # rather than borrowing Track 1's key.
    t1_key = env_var_name(Track1Config().provider_key_env)
    r = ModelRouter(track2=track2_config(), env={t1_key: "t1-present"})
    res = r.resolve(RouterSelectionInput(HINT_TASK_CLASS, requires_verification=True, track=TRACK_ID))
    assert res.selection.track == TRACK_ID
    assert res.available is False


# ---------------------------------------------------------------------------
# Capability registry — registered with track=2, least privilege
# ---------------------------------------------------------------------------

def test_track2_capabilities_are_track_2():
    for cap in track2_capabilities():
        assert cap.track == TRACK_ID
        assert cap.requires_verification is True
        # Least-privilege: a single purpose code, minimal scopes, no PII scope.
        assert cap.least_privilege.purpose
        assert cap.least_privilege.data_scopes
        assert all("pii" not in s.lower() for s in cap.least_privilege.data_scopes)


def test_register_track2_capabilities_on_fresh_registry():
    reg = CapabilityRegistry()
    caps = register_track2_capabilities(reg)
    assert len(caps) == len(reg.for_track(TRACK_ID))
    assert reg.for_track(1) == ()  # nothing on track 1 here


def test_track2_capabilities_dont_clash_with_default_track1_registry():
    # The default registry is all Track 1; Track 2 caps register alongside.
    reg = default_registry()
    assert all(c.track == 1 for c in reg.all())
    register_track2_capabilities(reg)
    assert len(reg.for_track(TRACK_ID)) == len(track2_capabilities())
    assert all(c.track == 1 for c in reg.for_track(1))


# ---------------------------------------------------------------------------
# Degrades gracefully with no endpoint (INVARIANT 4) — never fabricates
# ---------------------------------------------------------------------------

def test_adapter_unavailable_with_no_endpoint():
    adapter = Track2Adapter(settings=get_settings(env={}))  # no URL, no key
    res = adapter.run(task_class=HINT_TASK_CLASS, prompt="how do I start?")
    assert isinstance(res, Track2Result)
    assert res.track == TRACK_ID
    assert res.provider_available is False
    assert res.refused is True
    assert res.text is None
    assert "unavailable" in (res.detail or "").lower()
    assert TRACK2_ENDPOINT_URL_ENV_VAR in (res.detail or "")
    assert TRACK2_ENDPOINT_KEY_ENV_VAR in (res.detail or "")


def test_adapter_unavailable_with_url_but_no_key():
    env = {TRACK2_ENDPOINT_URL_ENV_VAR: "https://edge.invalid"}
    adapter = Track2Adapter(settings=get_settings(env=env), endpoint=_FakeEndpoint())
    res = adapter.run(task_class=HINT_TASK_CLASS, prompt="x")
    assert res.provider_available is False
    assert res.refused is True
    assert TRACK2_ENDPOINT_KEY_ENV_VAR in (res.detail or "")


def test_adapter_unavailable_with_key_but_no_seam():
    # Key + URL present, but no endpoint seam wired => unavailable, not fabricated.
    adapter = Track2Adapter(settings=get_settings(env=_env_with_track2()), endpoint=None)
    res = adapter.run(task_class=HINT_TASK_CLASS, prompt="x")
    assert res.provider_available is False
    assert res.refused is True
    assert res.text is None


def test_unavailable_result_never_leaks_key():
    adapter = Track2Adapter(settings=get_settings(env=_env_with_track2(key="super-secret-value")))
    res = adapter.run(task_class=HINT_TASK_CLASS, prompt="x")
    assert "super-secret-value" not in (res.detail or "")
    assert res.text is None


# ---------------------------------------------------------------------------
# The confidence gate applies to Track 2 output (INVARIANT 7)
# ---------------------------------------------------------------------------

def test_gate_serves_when_all_conditions_hold():
    adapter = Track2Adapter(
        settings=get_settings(env=_env_with_track2()),
        endpoint=_FakeEndpoint(text="Isolate x.", confidence=0.99),
        second_model=_AgreeingSecondModel(0.99),
    )
    res = adapter.run(task_class=HINT_TASK_CLASS, prompt="how do I start?")
    assert res.provider_available is True
    assert res.verification is not None
    assert res.verification.served is True
    assert res.refused is False
    assert res.text == "Isolate x."


def test_gate_withholds_when_second_model_abstains_default():
    # Default second model abstains => gate closed even with a live endpoint.
    adapter = Track2Adapter(
        settings=get_settings(env=_env_with_track2()),
        endpoint=_FakeEndpoint(text="Isolate x.", confidence=0.99),
    )
    res = adapter.run(task_class=HINT_TASK_CLASS, prompt="x")
    assert res.provider_available is True
    assert res.verification is not None
    assert res.verification.served is False
    assert res.refused is True
    assert res.text is None
    assert "second-model" in (res.verification.review_reason or "")


def test_gate_withholds_when_confidence_below_threshold():
    # Endpoint and second model agree, but confidence is below the gate.
    adapter = Track2Adapter(
        settings=get_settings(env=_env_with_track2()),
        endpoint=_FakeEndpoint(text="Isolate x.", confidence=0.50),
        second_model=_AgreeingSecondModel(0.50),
    )
    res = adapter.run(task_class=HINT_TASK_CLASS, prompt="x")
    assert res.verification is not None
    assert res.verification.served is False
    assert res.refused is True
    assert "confidence" in (res.verification.review_reason or "")


def test_gate_withholds_when_endpoint_returns_empty_text():
    adapter = Track2Adapter(
        settings=get_settings(env=_env_with_track2()),
        endpoint=_FakeEndpoint(text="", confidence=0.99),
        second_model=_AgreeingSecondModel(0.99),
    )
    res = adapter.run(task_class=HINT_TASK_CLASS, prompt="x")
    assert res.verification is not None
    assert res.verification.deterministic_checks_passed is False
    assert res.verification.served is False
    assert res.refused is True


def test_served_result_is_track_2():
    adapter = Track2Adapter(
        settings=get_settings(env=_env_with_track2()),
        endpoint=_FakeEndpoint(confidence=0.99),
        second_model=_AgreeingSecondModel(0.99),
    )
    res = adapter.run(task_class=INTENT_TASK_CLASS, prompt="I need help")
    assert res.track == TRACK_ID


# ---------------------------------------------------------------------------
# Config — Track 2 fields default to None under the shared prefix (INVARIANT 4)
# ---------------------------------------------------------------------------

def test_config_track2_fields_default_none():
    s = get_settings(env={})
    assert s.track2_endpoint_url is None
    assert s.track2_endpoint_key is None


def test_config_track2_fields_resolve_by_name():
    s = get_settings(env=_env_with_track2(url="https://edge.invalid", key="k"))
    assert s.track2_endpoint_url == "https://edge.invalid"
    assert s.track2_endpoint_key == "k"
