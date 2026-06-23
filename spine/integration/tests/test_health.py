"""Connector-health states: hysteresis, UNCONFIGURED, registry summary."""

from __future__ import annotations

from app import ConnectorHealth, HealthRegistry, HealthState, Standard
from app.connector import Connector
from app.adapters import OneRosterAdapter
from app.registry import ConnectorRegistry
from app.config import IntegrationSettings


def _health(**kw) -> ConnectorHealth:
    return ConnectorHealth(standard=Standard.ONEROSTER_1_2, connection_id="c1", **kw)


def test_unknown_until_first_probe():
    h = _health()
    assert h.state is HealthState.UNKNOWN


def test_unconfigured_when_not_configured():
    h = _health(configured=False)
    assert h.state is HealthState.UNCONFIGURED
    # even a successful probe stays UNCONFIGURED (no live endpoint route)
    h.record(True, latency_ms=10)
    assert h.state is HealthState.UNCONFIGURED


def test_healthy_after_recover_streak():
    h = _health(recover_streak=2)
    h.record(True, latency_ms=50)
    h.record(True, latency_ms=60)
    assert h.state is HealthState.HEALTHY


def test_down_after_fail_streak():
    h = _health(fail_streak=3)
    for _ in range(3):
        h.record(False, reason="timeout")
    assert h.state is HealthState.DOWN


def test_single_blip_does_not_flap_to_down():
    h = _health(fail_streak=3, recover_streak=2)
    h.record(True, latency_ms=20)
    h.record(False, reason="blip")  # one failure amid ok history
    assert h.state is HealthState.DEGRADED  # not DOWN


def test_elevated_latency_is_degraded_not_healthy():
    h = _health(recover_streak=2, latency_budget_ms=100)
    h.record(True, latency_ms=500)
    h.record(True, latency_ms=600)
    assert h.state is HealthState.DEGRADED


def test_recovery_back_to_healthy_after_failures():
    h = _health(fail_streak=3, recover_streak=2)
    for _ in range(3):
        h.record(False)
    assert h.state is HealthState.DOWN
    h.record(True, latency_ms=10)
    h.record(True, latency_ms=10)
    assert h.state is HealthState.HEALTHY


def test_registry_summary_and_any_down():
    reg = HealthRegistry()
    reg.register(_health())
    reg.record("c1", True, latency_ms=10)
    reg.record("c1", True, latency_ms=10)
    summary = reg.summary()
    assert len(summary) == 1
    assert summary[0]["state"] == HealthState.HEALTHY.value
    assert reg.any_down() is False


def test_safe_dict_has_no_pii_fields():
    h = _health()
    h.record(False, reason="connection refused")
    d = h.to_safe_dict()
    assert set(d) >= {"standard", "connection_id", "state", "last_reason"}
    assert d["last_reason"] == "connection refused"


def test_connector_probe_drives_state():
    adapter = OneRosterAdapter("oneroster:test", endpoint_route="https://route")
    assert adapter.configured is True
    assert adapter.degraded is False
    state = adapter.probe(True, latency_ms=12)
    state = adapter.probe(True, latency_ms=12)
    assert state is HealthState.HEALTHY


def test_connector_without_route_is_degraded():
    adapter = OneRosterAdapter("oneroster:test")  # no endpoint route
    assert adapter.degraded is True
    assert adapter.state is HealthState.UNCONFIGURED


def test_registry_reports_configured_vs_degraded(monkeypatch=None):
    # No env -> only the bundled content connectors (qti, scorm) are configured.
    settings = IntegrationSettings()
    reg = ConnectorRegistry(settings=settings)
    configured = set(reg.configured_standards())
    degraded = set(reg.degraded_standards())
    assert "qti" in configured and "scorm" in configured
    assert "lti-1.3" in degraded and "oneroster-1.2" in degraded
    # every connector is accounted for exactly once
    assert configured.isdisjoint(degraded)
    assert len(reg.all()) == len(configured) + len(degraded)
