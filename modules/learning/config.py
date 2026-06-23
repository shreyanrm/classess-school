"""Learning module configuration.

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded and never invented. Dotted names follow ``clss.<app>.<env>.<purpose>``
and map to ``CLSS_LEARNING_DEV_*`` env vars (uppercased, dots -> underscores).

The module holds NO credentials (INVARIANT 8 — agents hold no credentials).
Every cross-service call passes the gateway; this names the gateway URL var but
never stores a key value. With no provider configured the deterministic paths
work and event emission degrades to a clearly-labelled in-memory sink.

Import-safe: pydantic-settings is imported lazily inside :func:`get_settings`
so that merely importing this module (for type access / tooling) never requires
the dependency to be installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# Dotted secret/config names (names only — INVARIANT 4). Documented here so the
# README and the degraded-reasons report share a single source of truth.
ENV_GATEWAY_URL = "clss.learning.dev.gateway_url"
ENV_EVENT_SINK_URL = "clss.learning.dev.event_sink_url"
ENV_DATABASE_URL = "clss.learning.dev.database_url"
ENV_CROSSCHECK_MODEL_KEY = "clss.learning.dev.crosscheck_model_key"

_ENV_PREFIX = "CLSS_LEARNING_DEV_"


def _dotted_to_envvar(dotted: str) -> str:
    """clss.learning.dev.gateway_url -> CLSS_LEARNING_DEV_GATEWAY_URL."""
    return dotted.replace(".", "_").upper()


@dataclass(frozen=True)
class LearningSettings:
    """Resolved configuration. All optional: absence -> graceful degradation.

    Values are read from the environment by NAME. No secret value is ever
    defaulted to a literal here (INVARIANT 4) — only ``None``.
    """

    env: str = "dev"
    service_name: str = "learning"

    # The only egress. Every cross-service call (event store, ontology, the
    # intelligence engine when remote) passes the gateway. Unset -> degraded.
    gateway_url: str | None = None
    # Where emitted evidence events are POSTed (through the gateway). Unset ->
    # events are buffered to the in-memory degraded sink.
    event_sink_url: str | None = None
    # The read store the intelligence engine replays. Unset -> in-memory replay.
    database_url: str | None = None
    # Reserved name for a future second-model verification cross-check
    # (generate-and-verify, INVARIANT 7). No value is ever stored here.
    crosscheck_model_key: str | None = None

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
        """Names (NEVER values) of env vars whose absence keeps the module in a
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


_cached: LearningSettings | None = None


def get_settings(*, refresh: bool = False) -> LearningSettings:
    """Resolve settings from the environment (by name) once, then cache.

    Reads only environment variables — no file, no network, no secret literal.
    Pass ``refresh=True`` to re-read (e.g. after the environment changes in a
    test).
    """
    global _cached
    if _cached is not None and not refresh:
        return _cached
    _cached = LearningSettings(
        env=os.environ.get(_ENV_PREFIX + "ENV", "dev"),
        gateway_url=_read_env(ENV_GATEWAY_URL),
        event_sink_url=_read_env(ENV_EVENT_SINK_URL),
        database_url=_read_env(ENV_DATABASE_URL),
        crosscheck_model_key=_read_env(ENV_CROSSCHECK_MODEL_KEY),
    )
    return _cached
