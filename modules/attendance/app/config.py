"""Attendance intelligence configuration (B8 / d8).

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded and never invented. Dotted names follow ``clss.<app>.<env>.<purpose>``
and map to ``CLSS_ATTENDANCE_DEV_*`` env vars (uppercased, dots/dashes ->
underscores).

This module holds NO credentials (INVARIANT 8 — agents hold no credentials).
Every cross-service call passes the gateway; this names the gateway URL var but
never stores a key value. With no provider configured the deterministic paths
(multi-method capture, risk detection, signal reconciliation, staff attendance,
event emission) all work offline, and event emission degrades to a clearly
labelled in-memory append-only sink.

Import-safe: this module reads no environment VALUE and opens no connection at
import. Settings are resolved lazily by :func:`get_settings`, and only env-var
NAMES are ever referenced.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# Dotted secret/config NAMES (names only — INVARIANT 4). Single source of truth
# shared by the README and the degraded-reasons report.
ENV_GATEWAY_URL = "clss.attendance.dev.gateway_url"
ENV_EVENT_SINK_URL = "clss.attendance.dev.event_sink_url"
ENV_DATABASE_URL = "clss.attendance.dev.database_url"
# The A4 vision/voice orchestrator the photo-scan + voice roll-call methods would
# call (always behind the gateway, structured-output + confidence gate). Unset ->
# capture runs its deterministic path: it ASSISTS with whatever signals the
# caller supplies and the teacher confirms; nothing is ever auto-finalised.
ENV_ORCHESTRATOR_URL = "clss.attendance.dev.orchestrator_url"
# Optional on-device face / liveness verification provider (only where permitted
# and consented). Unset -> no biometric signal is produced; capture relies on the
# other methods. Never a default; biometrics are opt-in and consent-gated.
ENV_FACE_VERIFY_URL = "clss.attendance.dev.face_verify_url"
# The A1 consent authority — resolves consent + purpose for cross-context reads
# and for biometric capture. Unset -> only explicitly-supplied consent grants are
# honoured (fail-closed); biometrics stay off.
ENV_CONSENT_URL = "clss.attendance.dev.consent_url"
# The A5 workflow engine that carries an escalation / routed task to a qualified
# human (substitution ladder for staff, parent communication for chronic
# absence). Unset -> escalations stay local + pending; the trigger event is still
# emitted to the (in-memory) sink for replay.
ENV_WORKFLOW_URL = "clss.attendance.dev.workflow_url"

_ENV_PREFIX = "CLSS_ATTENDANCE_DEV_"

DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"


def env_var_name(dotted: str) -> str:
    """Map a dotted secret name to its OS environment variable key.

    ``clss.attendance.dev.gateway_url`` -> ``CLSS_ATTENDANCE_DEV_GATEWAY_URL``.
    """
    return dotted.replace(".", "_").replace("-", "_").upper()


@dataclass(frozen=True)
class AttendanceSettings:
    """Resolved configuration. Every field is optional; absence -> graceful
    degradation. No secret value is ever defaulted to a literal here
    (INVARIANT 4) — only ``None``.
    """

    env: str = "dev"
    service_name: str = "attendance"

    # The only egress. Every cross-service call (event store, orchestrator, face
    # verification, consent authority, workflow) passes the gateway. Unset ->
    # degraded.
    gateway_url: str | None = None
    event_sink_url: str | None = None
    database_url: str | None = None
    orchestrator_url: str | None = None
    face_verify_url: str | None = None
    consent_url: str | None = None
    workflow_url: str | None = None

    @property
    def has_gateway(self) -> bool:
        return bool(self.gateway_url)

    @property
    def has_event_sink(self) -> bool:
        """True only when BOTH the gateway and the sink are configured — every
        cross-service write passes the gateway, so a sink without a gateway is
        still degraded (we never write directly)."""
        return bool(self.gateway_url and self.event_sink_url)

    @property
    def has_orchestrator(self) -> bool:
        return bool(self.gateway_url and self.orchestrator_url)

    @property
    def has_face_verify(self) -> bool:
        return bool(self.gateway_url and self.face_verify_url)

    @property
    def has_consent_authority(self) -> bool:
        return bool(self.gateway_url and self.consent_url)

    @property
    def has_workflow(self) -> bool:
        return bool(self.gateway_url and self.workflow_url)

    def degraded_reasons(self) -> list[str]:
        """Dotted NAMES (NEVER values) of env vars whose absence keeps the
        module in degraded (deterministic, in-memory) mode."""
        missing: list[str] = []
        if not self.gateway_url:
            missing.append(ENV_GATEWAY_URL)
        if not self.event_sink_url:
            missing.append(ENV_EVENT_SINK_URL)
        if not self.database_url:
            missing.append(ENV_DATABASE_URL)
        if not self.orchestrator_url:
            missing.append(ENV_ORCHESTRATOR_URL)
        if not self.face_verify_url:
            missing.append(ENV_FACE_VERIFY_URL)
        if not self.consent_url:
            missing.append(ENV_CONSENT_URL)
        if not self.workflow_url:
            missing.append(ENV_WORKFLOW_URL)
        return missing


def _read_env(dotted: str) -> str | None:
    value = os.environ.get(env_var_name(dotted))
    if value is None:
        return None
    value = value.strip()
    return value or None


_cached: AttendanceSettings | None = None


def get_settings(*, refresh: bool = False) -> AttendanceSettings:
    """Resolve settings from the environment (by NAME) once, then cache.

    Reads only environment variables — no file, no network, no secret literal.
    Pass ``refresh=True`` to re-read (e.g. after the environment changes in a
    test).
    """
    global _cached
    if _cached is not None and not refresh:
        return _cached
    _cached = AttendanceSettings(
        env=os.environ.get(_ENV_PREFIX + "ENV", "dev"),
        gateway_url=_read_env(ENV_GATEWAY_URL),
        event_sink_url=_read_env(ENV_EVENT_SINK_URL),
        database_url=_read_env(ENV_DATABASE_URL),
        orchestrator_url=_read_env(ENV_ORCHESTRATOR_URL),
        face_verify_url=_read_env(ENV_FACE_VERIFY_URL),
        consent_url=_read_env(ENV_CONSENT_URL),
        workflow_url=_read_env(ENV_WORKFLOW_URL),
    )
    return _cached
