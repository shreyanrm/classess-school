"""Personalization module configuration (implicit profiling engine).

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded, never logged, never invented, never ``NEXT_PUBLIC_*``. The dotted
convention is ``clss.<app>.<env>.<purpose>`` which maps to
``CLSS_PERSONALIZATION_DEV_*`` env vars (uppercased, dots/dashes -> underscores).

This module READS behavioural signals (governed, consent + age-tier-gated) and
EMITS ``profile.updated`` events. Every cross-service call passes the gateway
(INVARIANT 3); the module holds NO credentials (INVARIANT 8) — it names the
gateway URL and the bearer-token env var but never stores a value.

With nothing configured the deterministic paths work entirely in-process and
offline: inference replays from in-memory signals and emitted events buffer to a
clearly-labelled in-memory append-only sink. The consent + age-tier gate still
denies-by-default; absence of a remote consent authority never opens a door.

Import-safe: no I/O, no network, no secret value read at import beyond
``os.environ`` lookups by name inside :func:`get_settings`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"

# The only egress. Every governed signal read / event write passes the gateway.
ENV_GATEWAY_URL = "clss.personalization.dev.gateway_url"
# Bearer issued by identity and presented at the gateway wall. NEVER a literal.
ENV_GATEWAY_TOKEN = "clss.personalization.dev.gateway_token"
# The governed signal read-view service (behavioural events). Unset -> in-memory.
ENV_SIGNAL_READ_URL = "clss.personalization.dev.signal_read_url"
# The consent-authority service consulted on every inference. Unset -> the
# deterministic in-process gate (still denied-by-default, never fail-open).
ENV_CONSENT_AUTHORITY_URL = "clss.personalization.dev.consent_authority_url"
# Where ``profile.updated`` events are POSTed (through the gateway). Unset ->
# events buffered to the in-memory append-only sink.
ENV_EVENT_SINK_URL = "clss.personalization.dev.event_sink_url"

_ENV_PREFIX = "CLSS_PERSONALIZATION_DEV_"


def _dotted_to_envvar(dotted: str) -> str:
    """clss.personalization.dev.gateway_url -> CLSS_PERSONALIZATION_DEV_GATEWAY_URL."""
    return dotted.replace(".", "_").replace("-", "_").upper()


def _read_env(dotted: str) -> str | None:
    value = os.environ.get(_dotted_to_envvar(dotted))
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class PersonalizationSettings:
    """Resolved configuration. All optional: absence -> graceful degradation.

    No secret value is ever defaulted to a literal here (INVARIANT 4) — only
    ``None``. The booleans report capability, never a value.
    """

    env: str = "dev"
    service_name: str = "personalization"

    gateway_url: str | None = None
    gateway_token: str | None = None
    signal_read_url: str | None = None
    consent_authority_url: str | None = None
    event_sink_url: str | None = None

    @property
    def has_gateway(self) -> bool:
        return bool(self.gateway_url and self.gateway_token)

    @property
    def has_signal_reads(self) -> bool:
        """True only when the gateway AND the read-view service are configured —
        every read passes the gateway, so a read URL without a gateway is still
        degraded (we never read directly)."""
        return bool(self.has_gateway and self.signal_read_url)

    @property
    def has_consent_authority(self) -> bool:
        """True when a remote consent authority is wired. When false the gate
        still runs in-process and still denies-by-default."""
        return bool(self.has_gateway and self.consent_authority_url)

    @property
    def has_event_sink(self) -> bool:
        return bool(self.has_gateway and self.event_sink_url)

    def degraded_reasons(self) -> list[str]:
        """Names (NEVER values) of env vars whose absence keeps the module in a
        degraded (deterministic, in-memory) mode."""
        missing: list[str] = []
        if not self.gateway_url:
            missing.append(ENV_GATEWAY_URL)
        if not self.gateway_token:
            missing.append(ENV_GATEWAY_TOKEN)
        if not self.signal_read_url:
            missing.append(ENV_SIGNAL_READ_URL)
        if not self.consent_authority_url:
            missing.append(ENV_CONSENT_AUTHORITY_URL)
        if not self.event_sink_url:
            missing.append(ENV_EVENT_SINK_URL)
        return missing


_cached: PersonalizationSettings | None = None


def get_settings(*, refresh: bool = False) -> PersonalizationSettings:
    """Resolve settings from the environment (by name) once, then cache.

    Reads only environment variables — no file, no network, no secret literal.
    Pass ``refresh=True`` to re-read (e.g. after the environment changes).
    """
    global _cached
    if _cached is not None and not refresh:
        return _cached
    _cached = PersonalizationSettings(
        env=os.environ.get(_ENV_PREFIX + "ENV", "dev"),
        gateway_url=_read_env(ENV_GATEWAY_URL),
        gateway_token=_read_env(ENV_GATEWAY_TOKEN),
        signal_read_url=_read_env(ENV_SIGNAL_READ_URL),
        consent_authority_url=_read_env(ENV_CONSENT_AUTHORITY_URL),
        event_sink_url=_read_env(ENV_EVENT_SINK_URL),
    )
    return _cached


__all__ = [
    "DOTTED_CONVENTION",
    "ENV_GATEWAY_URL",
    "ENV_GATEWAY_TOKEN",
    "ENV_SIGNAL_READ_URL",
    "ENV_CONSENT_AUTHORITY_URL",
    "ENV_EVENT_SINK_URL",
    "PersonalizationSettings",
    "get_settings",
]
