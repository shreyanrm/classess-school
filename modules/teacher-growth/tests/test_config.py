"""Config: env-var NAMES only, no secret literal, graceful degradation."""

from __future__ import annotations

from app.config import (
    COACHING_VISIBILITY,
    ENV_GATEWAY_URL,
    TeacherGrowthSettings,
    env_var_name,
    get_settings,
)


def test_dotted_name_maps_to_os_env_key():
    assert env_var_name("clss.teachergrowth.dev.gateway_url") == \
        "CLSS_TEACHERGROWTH_DEV_GATEWAY_URL"


def test_default_settings_are_degraded_and_name_missing_vars():
    settings = TeacherGrowthSettings()
    assert settings.has_gateway is False
    assert settings.has_event_sink is False
    reasons = settings.degraded_reasons()
    # Reports dotted NAMES, never values.
    assert ENV_GATEWAY_URL in reasons
    for r in reasons:
        assert r.startswith("clss.teachergrowth.dev.")


def test_coaching_visibility_is_fixed_teacher_first():
    settings = TeacherGrowthSettings()
    assert settings.coaching_visibility == COACHING_VISIBILITY == "teacher_first"
    assert settings.coaching_is_teacher_first is True


def test_sink_needs_both_gateway_and_sink_url():
    # A sink without a gateway is still degraded (every write passes the gateway).
    only_sink = TeacherGrowthSettings(event_sink_url="https://sink.example")
    assert only_sink.has_event_sink is False
    both = TeacherGrowthSettings(
        gateway_url="https://gw.example", event_sink_url="https://sink.example"
    )
    assert both.has_event_sink is True


def test_get_settings_reads_no_secret_value(monkeypatch):
    # With nothing set, settings resolve to degraded; no literal is invented.
    for key in (
        "CLSS_TEACHERGROWTH_DEV_GATEWAY_URL",
        "CLSS_TEACHERGROWTH_DEV_EVENT_SINK_URL",
        "CLSS_TEACHERGROWTH_DEV_DATABASE_URL",
        "CLSS_TEACHERGROWTH_DEV_WORKFLOW_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = get_settings(refresh=True)
    assert settings.gateway_url is None
    assert settings.has_gateway is False
