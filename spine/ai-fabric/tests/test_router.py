"""Tests for the model router: tier selection, track separation, env-by-name.

Import-safe, no network.
"""

from __future__ import annotations

from app.router import (
    ModelRouter,
    ModelTier,
    RouterSelectionInput,
    Track1Config,
    Track2Config,
    env_var_name,
)


def test_env_var_name_convention():
    assert env_var_name("clss.aifabric.dev.track1_provider_key") == \
        "CLSS_AIFABRIC_DEV_TRACK1_PROVIDER_KEY"


# -- tier selection --------------------------------------------------------

def test_mapped_task_class_to_frontier():
    r = ModelRouter(env={})
    sel = r.select_tier(RouterSelectionInput("evaluation.deep-reasoning", requires_verification=True))
    assert sel.tier is ModelTier.FRONTIER


def test_high_frequency_to_edge():
    r = ModelRouter(env={})
    sel = r.select_tier(RouterSelectionInput("conversation.companion-turn", requires_verification=True))
    assert sel.tier is ModelTier.EDGE


def test_volume_to_mid():
    r = ModelRouter(env={})
    sel = r.select_tier(RouterSelectionInput("content.generate-practice-item", requires_verification=True))
    assert sel.tier is ModelTier.MID


def test_unknown_high_difficulty_to_frontier():
    r = ModelRouter(env={})
    sel = r.select_tier(RouterSelectionInput("unknown.task", requires_verification=True, difficulty=0.95))
    assert sel.tier is ModelTier.FRONTIER


def test_unknown_latency_sensitive_to_edge():
    r = ModelRouter(env={})
    sel = r.select_tier(RouterSelectionInput("unknown.task", requires_verification=True, latency_sensitive=True))
    assert sel.tier is ModelTier.EDGE


def test_unknown_default_to_mid():
    r = ModelRouter(env={})
    sel = r.select_tier(RouterSelectionInput("unknown.task", requires_verification=True))
    assert sel.tier is ModelTier.MID


# -- track 1: env-by-name, no key => unavailable ---------------------------

def test_track1_no_key_is_unavailable_not_fabricated():
    r = ModelRouter(env={})  # no provider key in env
    res = r.resolve(RouterSelectionInput("content.generate-practice-item", requires_verification=True, track=1))
    assert res.available is False
    assert res.model is None
    assert "CLSS_AIFABRIC_DEV_TRACK1_PROVIDER_KEY" in (res.unavailable_reason or "")


def test_track1_with_key_resolves():
    key = env_var_name(Track1Config().provider_key_env)
    r = ModelRouter(env={key: "present-by-name-only"})
    res = r.resolve(RouterSelectionInput("content.generate-practice-item", requires_verification=True, track=1))
    assert res.available is True
    assert res.model is not None
    assert res.selection.tier is ModelTier.MID


# -- track 2: the reserved slot, distinct, disabled by default -------------

def test_track2_disabled_by_default_is_reserved_slot():
    r = ModelRouter(env={})
    res = r.resolve(RouterSelectionInput("content.generate-practice-item", requires_verification=True, track=2))
    assert res.available is False
    assert "reserved slot" in (res.unavailable_reason or "").lower()


def test_track2_is_distinct_structure_from_track1():
    # Distinct types, distinct env var names — INVARIANT 11.
    t1 = Track1Config()
    t2 = Track2Config()
    assert type(t1) is not type(t2)
    assert t1.provider_key_env != t2.provider_key_env
    assert t1.owner != t2.owner


def test_track2_enabled_resolves_independently_of_track1():
    # Filling Track 2 is config-only: enable + bind a model + provide its key.
    key = env_var_name("clss.aifabric.dev.track2_endpoint_key")
    t2 = Track2Config(enabled=True, tier_models={ModelTier.EDGE: "edge-slm-local"})
    r = ModelRouter(track2=t2, env={key: "present"})
    res = r.resolve(RouterSelectionInput("conversation.companion-turn", requires_verification=True, track=2))
    assert res.available is True
    assert res.model is not None
    assert res.model.model_label == "edge-slm-local"
    assert res.selection.track == 2


def test_selection_never_crosses_track():
    # A track-2 intent stays on track 2 even though track 1 has a key.
    k1 = env_var_name(Track1Config().provider_key_env)
    r = ModelRouter(env={k1: "present"})
    res = r.resolve(RouterSelectionInput("conversation.companion-turn", requires_verification=True, track=2))
    assert res.selection.track == 2
    assert res.available is False  # track 2 still disabled; never borrows track 1
