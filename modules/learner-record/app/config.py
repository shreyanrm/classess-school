"""Learner-record module configuration (B8).

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded, never logged, never invented. The dotted convention is
``clss.<app>.<env>.<purpose>`` which maps to ``CLSS_LEARNER_RECORD_DEV_*`` env
vars (uppercased, dots -> underscores).

This module READS governed, consent + purpose-gated views of the learner graph
and the evidence store; it never reads them directly and never in bulk. Every
cross-service call passes the gateway (INVARIANT 3). The module holds NO
credentials (INVARIANT 8) — it names the gateway URL and the bearer-token env
var but never stores a value.

With nothing configured the deterministic paths work and every read view is
served from an in-memory, append-only fixture so the module imports, the gate
still denies-by-default, and the test suite passes with no network or DB.

Import-safe: no I/O, no network, no secret value is read at import time beyond
``os.environ`` lookups by name inside :func:`get_settings`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Dotted secret/config NAMES (names only — INVARIANT 4). A single source of
# truth shared by the README and the degraded-reasons report.
DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"

# The only egress. Every governed read of the learner graph / evidence store
# passes the gateway. Unset -> degraded (in-memory fixture views).
ENV_GATEWAY_URL = "clss.learner-record.dev.gateway_url"
# Bearer issued by identity (A1) and presented at the gateway wall. NEVER a
# literal; read from the environment by name only.
ENV_GATEWAY_TOKEN = "clss.learner-record.dev.gateway_token"
# The governed read-view service for the learner graph + evidence store (A3).
# Unset -> the in-memory degraded read source.
ENV_GRAPH_READ_URL = "clss.learner-record.dev.graph_read_url"
# The consent-authority service (A1/A7) consulted on every read. Unset -> the
# deterministic in-process gate (still denied-by-default).
ENV_CONSENT_AUTHORITY_URL = "clss.learner-record.dev.consent_authority_url"
# Where portfolio/credential events are POSTed (through the gateway). Unset ->
# events buffered to the in-memory append-only sink.
ENV_EVENT_SINK_URL = "clss.learner-record.dev.event_sink_url"
# Signing key NAME for verifiable credentials. The value never lives in code;
# absent -> credentials are issued in unsigned-draft state, never as verified.
ENV_CREDENTIAL_SIGNING_KEY = "clss.learner-record.dev.credential_signing_key"

_ENV_PREFIX = "CLSS_LEARNER_RECORD_DEV_"


def _dotted_to_envvar(dotted: str) -> str:
    """clss.learner-record.dev.gateway_url -> CLSS_LEARNER_RECORD_DEV_GATEWAY_URL."""
    return dotted.replace(".", "_").replace("-", "_").upper()


def _read_env(dotted: str) -> str | None:
    value = os.environ.get(_dotted_to_envvar(dotted))
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class LearnerRecordSettings:
    """Resolved configuration. All optional: absence -> graceful degradation.

    No secret value is ever defaulted to a literal here (INVARIANT 4) — only
    ``None``. The booleans below report capability, never a value.
    """

    env: str = "dev"
    service_name: str = "learner-record"

    gateway_url: str | None = None
    gateway_token: str | None = None
    graph_read_url: str | None = None
    consent_authority_url: str | None = None
    event_sink_url: str | None = None
    credential_signing_key: str | None = None

    @property
    def has_gateway(self) -> bool:
        return bool(self.gateway_url and self.gateway_token)

    @property
    def has_graph_reads(self) -> bool:
        """True only when the gateway AND the read-view service are configured —
        every read passes the gateway, so a read URL without a gateway is still
        degraded (we never read directly)."""
        return bool(self.has_gateway and self.graph_read_url)

    @property
    def has_consent_authority(self) -> bool:
        """True when a remote consent authority is wired. When false the gate
        still runs in-process and still denies-by-default."""
        return bool(self.has_gateway and self.consent_authority_url)

    @property
    def has_event_sink(self) -> bool:
        return bool(self.has_gateway and self.event_sink_url)

    @property
    def can_sign_credentials(self) -> bool:
        """A credential reaches 'verified' only when a signing key is present.
        Absent -> credentials stay in unsigned-draft state (never faked)."""
        return bool(self.credential_signing_key)

    def degraded_reasons(self) -> list[str]:
        """Names (NEVER values) of env vars whose absence keeps the module in a
        degraded (deterministic, in-memory) mode."""
        missing: list[str] = []
        if not self.gateway_url:
            missing.append(ENV_GATEWAY_URL)
        if not self.gateway_token:
            missing.append(ENV_GATEWAY_TOKEN)
        if not self.graph_read_url:
            missing.append(ENV_GRAPH_READ_URL)
        if not self.consent_authority_url:
            missing.append(ENV_CONSENT_AUTHORITY_URL)
        if not self.event_sink_url:
            missing.append(ENV_EVENT_SINK_URL)
        if not self.credential_signing_key:
            missing.append(ENV_CREDENTIAL_SIGNING_KEY)
        return missing


_cached: LearnerRecordSettings | None = None


def get_settings(*, refresh: bool = False) -> LearnerRecordSettings:
    """Resolve settings from the environment (by name) once, then cache.

    Reads only environment variables — no file, no network, no secret literal.
    Pass ``refresh=True`` to re-read (e.g. after the environment changes in a
    test).
    """
    global _cached
    if _cached is not None and not refresh:
        return _cached
    _cached = LearnerRecordSettings(
        env=os.environ.get(_ENV_PREFIX + "ENV", "dev"),
        gateway_url=_read_env(ENV_GATEWAY_URL),
        gateway_token=_read_env(ENV_GATEWAY_TOKEN),
        graph_read_url=_read_env(ENV_GRAPH_READ_URL),
        consent_authority_url=_read_env(ENV_CONSENT_AUTHORITY_URL),
        event_sink_url=_read_env(ENV_EVENT_SINK_URL),
        credential_signing_key=_read_env(ENV_CREDENTIAL_SIGNING_KEY),
    )
    return _cached
