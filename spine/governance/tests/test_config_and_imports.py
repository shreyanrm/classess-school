"""Import-safety + env-only config. No network/DB.

INVARIANT 4 — secrets are env-only, read by NAME, never hardcoded.
"""

from __future__ import annotations

import importlib


def test_all_modules_import_safely():
    for name in (
        "app.audit", "app.breakglass", "app.control_centre",
        "app.consent", "app.child_safety", "app.tenancy",
        "app.config", "app.models",
    ):
        importlib.import_module(name)


def test_settings_default_to_none_without_env():
    from app.config import get_settings

    s = get_settings(env={})
    assert s.audit_database_url is None
    assert s.child_safety_classifier_key is None
    assert s.escalation_webhook_key is None


def test_settings_read_by_prefixed_name():
    from app.config import ENV_PREFIX, get_settings

    env = {ENV_PREFIX + "AUDIT_DATABASE_URL": "postgres://x"}
    s = get_settings(env=env)
    assert s.audit_database_url == "postgres://x"


def test_track1_and_track2_keys_are_separate_fields():
    # INVARIANT 11: the two tracks never share a config slot.
    from app.config import ENV_PREFIX, get_settings

    env = {
        ENV_PREFIX + "CHILD_SAFETY_CLASSIFIER_KEY": "track1-key",
        ENV_PREFIX + "CHILD_SAFETY_EDGE_MODEL_KEY": "track2-key",
    }
    s = get_settings(env=env)
    assert s.child_safety_classifier_key == "track1-key"
    assert s.child_safety_edge_model_key == "track2-key"
    assert s.child_safety_classifier_key != s.child_safety_edge_model_key


def test_no_hardcoded_secret_values_in_config_source():
    # The config module names secrets but never embeds a value.
    import pathlib

    src = pathlib.Path(__file__).resolve().parents[1] / "app" / "config.py"
    text = src.read_text()
    # Field defaults are None only; no obvious key-looking literals.
    assert "= None" in text
    for needle in ("postgres://", "sk-", "Bearer "):
        assert needle not in text
