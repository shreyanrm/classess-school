"""Config: env-only by NAME, no secret value, graceful degradation."""

from __future__ import annotations

from app.config import (
    ENV_CREDENTIAL_SIGNING_KEY,
    ENV_GATEWAY_TOKEN,
    ENV_GATEWAY_URL,
    LearnerRecordSettings,
    _dotted_to_envvar,
    get_settings,
)


def test_dotted_names_follow_the_convention():
    assert ENV_GATEWAY_URL == "clss.learner-record.dev.gateway_url"
    assert ENV_GATEWAY_TOKEN == "clss.learner-record.dev.gateway_token"


def test_dotted_maps_to_envvar():
    assert _dotted_to_envvar(ENV_GATEWAY_URL) == "CLSS_LEARNER_RECORD_DEV_GATEWAY_URL"
    assert _dotted_to_envvar(ENV_CREDENTIAL_SIGNING_KEY) == "CLSS_LEARNER_RECORD_DEV_CREDENTIAL_SIGNING_KEY"


def test_empty_settings_are_fully_degraded():
    s = LearnerRecordSettings()
    assert s.has_gateway is False
    assert s.has_graph_reads is False
    assert s.has_consent_authority is False
    assert s.has_event_sink is False
    assert s.can_sign_credentials is False
    # Degraded reasons name (never value) every missing var.
    reasons = s.degraded_reasons()
    assert ENV_GATEWAY_URL in reasons
    assert ENV_CREDENTIAL_SIGNING_KEY in reasons


def test_read_url_without_gateway_is_still_degraded():
    # Every read passes the gateway — a read URL alone never enables reads.
    s = LearnerRecordSettings(graph_read_url="https://example/read")
    assert s.has_graph_reads is False


def test_get_settings_reads_env_by_name(monkeypatch):
    monkeypatch.setenv("CLSS_LEARNER_RECORD_DEV_CREDENTIAL_SIGNING_KEY", "value-from-env")
    s = get_settings(refresh=True)
    assert s.can_sign_credentials is True
    # The value came from the environment, not a literal in code.
    assert s.credential_signing_key == "value-from-env"
    monkeypatch.delenv("CLSS_LEARNER_RECORD_DEV_CREDENTIAL_SIGNING_KEY")
    get_settings(refresh=True)  # reset cache for other tests
