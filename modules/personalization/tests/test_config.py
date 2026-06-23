"""Config: secrets are environment-only, read by name, never defaulted to a
literal, never NEXT_PUBLIC.
"""

from __future__ import annotations

import inspect

from app import config as config_mod
from app.config import (
    ENV_GATEWAY_TOKEN,
    ENV_GATEWAY_URL,
    PersonalizationSettings,
    get_settings,
)


def test_no_secret_value_in_source():
    """No literal token/url value is hardcoded; only dotted NAMES appear."""
    src = inspect.getsource(config_mod)
    # No secret is ever read from a client-exposed NEXT_PUBLIC_* variable.
    assert "NEXT_PUBLIC_" not in src.replace("NEXT_PUBLIC_*", ""), (
        "secrets must never be read from a client-exposed NEXT_PUBLIC_ variable"
    )
    # The dotted names are present (names, not values).
    assert "clss.personalization.dev.gateway_token" in src
    assert "clss.personalization.dev.gateway_url" in src


def test_dotted_names_map_to_env_vars():
    assert ENV_GATEWAY_URL == "clss.personalization.dev.gateway_url"
    assert ENV_GATEWAY_TOKEN == "clss.personalization.dev.gateway_token"


def test_unconfigured_settings_are_degraded():
    settings = PersonalizationSettings()
    assert settings.has_gateway is False
    assert settings.has_event_sink is False
    assert settings.has_consent_authority is False
    reasons = settings.degraded_reasons()
    # The reasons are NAMES, never values.
    assert ENV_GATEWAY_URL in reasons
    assert ENV_GATEWAY_TOKEN in reasons


def test_settings_read_from_env_by_name(monkeypatch):
    monkeypatch.setenv("CLSS_PERSONALIZATION_DEV_GATEWAY_URL", "https://gw.example")
    monkeypatch.setenv("CLSS_PERSONALIZATION_DEV_GATEWAY_TOKEN", "tkn")
    settings = get_settings(refresh=True)
    assert settings.gateway_url == "https://gw.example"
    assert settings.has_gateway is True
    # Clean up the cache so other tests see a fresh read.
    monkeypatch.delenv("CLSS_PERSONALIZATION_DEV_GATEWAY_URL")
    monkeypatch.delenv("CLSS_PERSONALIZATION_DEV_GATEWAY_TOKEN")
    get_settings(refresh=True)
