"""Import-safety: every module imports with no network, no provider, no training."""

from __future__ import annotations

import importlib


def test_all_modules_import():
    for name in (
        "app",
        "app.config",
        "app.capture",
        "app.consent_gate",
        "app.dataset",
        "app.curate",
        "app.eval",
        "app.finetune",
        "app.registry",
        "app.loop",
        "app.events",
    ):
        importlib.import_module(name)


def test_settings_default_to_unset_without_env():
    from app.config import get_settings

    s = get_settings(env={})
    assert s.training_endpoint is None
    assert s.training_key is None
    assert s.training_configured() is False
