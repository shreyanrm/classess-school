"""Institution module configuration.

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded and never invented. Dotted names follow ``clss.<app>.<env>.<purpose>``
and map to ``CLSS_INSTITUTION_DEV_*`` env vars (uppercased, dots -> underscores).

The module holds NO credentials (INVARIANT 8 — agents hold no credentials).
Every cross-service call passes the gateway; this names the gateway URL var but
never stores a key value. With no provider configured the deterministic paths
work and event emission degrades to returning the event object.

Import-safe: nothing here imports a third-party package at module load, so
merely importing this module (for type access / tooling) never requires a
dependency to be installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# Dotted secret/config names (NAMES only — INVARIANT 4). Documented here so the
# README and the degraded-reasons report share a single source of truth.
ENV_GATEWAY_URL = "clss.institution.dev.gateway_url"
ENV_EVENT_SINK_URL = "clss.institution.dev.event_sink_url"
ENV_DATABASE_URL = "clss.institution.dev.database_url"
ENV_IDENTITY_URL = "clss.institution.dev.identity_url"
ENV_ONTOLOGY_URL = "clss.institution.dev.ontology_url"

_ENV_PREFIX = "CLSS_INSTITUTION_DEV_"


def _dotted_to_envvar(dotted: str) -> str:
    """clss.institution.dev.gateway_url -> CLSS_INSTITUTION_DEV_GATEWAY_URL."""
    return dotted.replace(".", "_").upper()


@dataclass(frozen=True)
class InstitutionSettings:
    """Resolved configuration. All optional: absence -> graceful degradation.

    Values are read from the environment by NAME. No secret value is ever
    defaulted to a literal here (INVARIANT 4) — only ``None``.
    """

    env: str = "dev"
    service_name: str = "institution"

    # The only egress. Every cross-service call (event store, the identity
    # service for membership/consent resolution, the ontology service for
    # board/grade mapping) passes the gateway. Unset -> degraded.
    gateway_url: str | None = None
    # Where emitted structure/roster/policy events are POSTed (through the
    # gateway). Unset -> events are returned to the caller, never sent.
    event_sink_url: str | None = None
    # The canonical store for institution config. Unset -> in-memory only.
    database_url: str | None = None
    # Identity service base (membership + consent resolution). Unset -> the
    # module trusts caller-supplied opaque ids and never resolves PII.
    identity_url: str | None = None
    # Ontology service base (board -> grade -> subject mapping). Unset -> the
    # blueprint accepts opaque ontology ids without remote validation.
    ontology_url: str | None = None

    @property
    def has_gateway(self) -> bool:
        return bool(self.gateway_url)

    @property
    def has_event_sink(self) -> bool:
        """True only when BOTH the gateway and the sink are configured — every
        cross-service write passes the gateway, so a sink without a gateway is
        still degraded (we never write directly)."""
        return bool(self.gateway_url and self.event_sink_url)

    def degraded_reasons(self) -> list[str]:
        """NAMES (never values) of env vars whose absence keeps the module in a
        degraded (deterministic, in-memory) mode."""
        missing: list[str] = []
        if not self.gateway_url:
            missing.append(ENV_GATEWAY_URL)
        if not self.event_sink_url:
            missing.append(ENV_EVENT_SINK_URL)
        if not self.database_url:
            missing.append(ENV_DATABASE_URL)
        return missing


def _read_env(dotted: str) -> str | None:
    value = os.environ.get(_dotted_to_envvar(dotted))
    if value is None:
        return None
    value = value.strip()
    return value or None


_cached: InstitutionSettings | None = None


def get_settings(*, refresh: bool = False) -> InstitutionSettings:
    """Resolve settings from the environment (by name) once, then cache.

    Reads only environment variables — no file, no network, no secret literal.
    Pass ``refresh=True`` to re-read (e.g. after the environment changes in a
    test).
    """
    global _cached
    if _cached is not None and not refresh:
        return _cached
    _cached = InstitutionSettings(
        env=os.environ.get(_ENV_PREFIX + "ENV", "dev"),
        gateway_url=_read_env(ENV_GATEWAY_URL),
        event_sink_url=_read_env(ENV_EVENT_SINK_URL),
        database_url=_read_env(ENV_DATABASE_URL),
        identity_url=_read_env(ENV_IDENTITY_URL),
        ontology_url=_read_env(ENV_ONTOLOGY_URL),
    )
    return _cached
