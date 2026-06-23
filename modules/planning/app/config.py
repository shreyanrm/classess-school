"""Teacher planning & instruction design configuration (d6).

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded and never invented. Dotted names follow ``clss.<app>.<env>.<purpose>``
and map to ``CLSS_PLANNING_DEV_*`` env vars (uppercased, dots/dashes ->
underscores).

This module holds NO credentials (INVARIANT 8 — agents hold no credentials).
Every cross-service call passes the gateway; this names the gateway URL var but
never stores a key value. With no provider configured the deterministic paths
(plan generation, day-to-day adaptation, differentiation banding, the diary's
planned-vs-delivered reconciliation) all work, and event emission degrades to a
clearly-labelled in-memory append-only sink.

Import-safe: this module reads no environment VALUE and opens no connection at
import. Settings are resolved lazily by :func:`get_settings`, and only env-var
NAMES are ever referenced.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# Dotted secret/config NAMES (names only — INVARIANT 4). Single source of truth
# shared by the README and the degraded-reasons report.
ENV_GATEWAY_URL = "clss.planning.dev.gateway_url"
ENV_EVENT_SINK_URL = "clss.planning.dev.event_sink_url"
ENV_DATABASE_URL = "clss.planning.dev.database_url"
ENV_CONTENT_URL = "clss.planning.dev.content_url"
ENV_WORKFLOW_URL = "clss.planning.dev.workflow_url"

_ENV_PREFIX = "CLSS_PLANNING_DEV_"

DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"


def env_var_name(dotted: str) -> str:
    """Map a dotted secret name to its OS environment variable key.

    ``clss.planning.dev.gateway_url`` -> ``CLSS_PLANNING_DEV_GATEWAY_URL``.
    """
    return dotted.replace(".", "_").replace("-", "_").upper()


@dataclass(frozen=True)
class PlanningSettings:
    """Resolved configuration. Every field is optional; absence -> graceful
    degradation. No secret value is ever defaulted to a literal here
    (INVARIANT 4) — only ``None``.
    """

    env: str = "dev"
    service_name: str = "planning"

    # The only egress. Every cross-service call (event store, the content
    # engine, the intelligence layer for mastery/gap reads, the workflow engine
    # that routes plans for approval) passes the gateway. Unset -> degraded.
    gateway_url: str | None = None
    # Where emitted plan/diary events are POSTed (through the gateway). Unset ->
    # events buffer to the in-memory sink.
    event_sink_url: str | None = None
    # The operational store (plan rows, diary entries). Unset -> in-memory.
    database_url: str | None = None
    # The content engine that generates lesson material, misconceptions, and
    # checks for understanding. Unset -> plans carry structure + opaque refs
    # only, no generated body.
    content_url: str | None = None
    # The A5 workflow engine that routes a plan to a coordinator/head for
    # approval. Unset -> approvals stay local + pending.
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
    def has_content(self) -> bool:
        return bool(self.gateway_url and self.content_url)

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
        if not self.content_url:
            missing.append(ENV_CONTENT_URL)
        if not self.workflow_url:
            missing.append(ENV_WORKFLOW_URL)
        return missing


def _read_env(dotted: str) -> str | None:
    value = os.environ.get(env_var_name(dotted))
    if value is None:
        return None
    value = value.strip()
    return value or None


_cached: PlanningSettings | None = None


def get_settings(*, refresh: bool = False) -> PlanningSettings:
    """Resolve settings from the environment (by NAME) once, then cache.

    Reads only environment variables — no file, no network, no secret literal.
    Pass ``refresh=True`` to re-read (e.g. after the environment changes in a
    test).
    """
    global _cached
    if _cached is not None and not refresh:
        return _cached
    _cached = PlanningSettings(
        env=os.environ.get(_ENV_PREFIX + "ENV", "dev"),
        gateway_url=_read_env(ENV_GATEWAY_URL),
        event_sink_url=_read_env(ENV_EVENT_SINK_URL),
        database_url=_read_env(ENV_DATABASE_URL),
        content_url=_read_env(ENV_CONTENT_URL),
        workflow_url=_read_env(ENV_WORKFLOW_URL),
    )
    return _cached
