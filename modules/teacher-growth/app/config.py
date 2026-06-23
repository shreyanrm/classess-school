"""Teacher growth configuration (B10).

SECURITY INVARIANT 4: secrets are environment-only, read by NAME, never
hardcoded and never invented. Dotted names follow ``clss.<app>.<env>.<purpose>``
and map to ``CLSS_TEACHERGROWTH_DEV_*`` env vars (uppercased, dots/dashes ->
underscores).

This module holds NO credentials (INVARIANT 8 — agents hold no credentials).
Every cross-service call passes the gateway; this names the gateway URL var but
never stores a key value. With no provider configured the deterministic paths
(talk-ratio / questioning / equity / wait-time math, the quality-review
workflow, continuity handover notes) all work, and coaching-signal event
emission degrades to a clearly-labelled in-memory sink.

Privacy posture (B10-specific): coaching signals are PRIVATE to the teacher.
The ``coaching_visibility`` setting is ``teacher_first`` and is NOT an env
secret — it is a fixed product invariant exposed here so callers can read it,
not override it. There is no configuration that turns coaching into an open,
punitive ranking.

Import-safe: this module reads no environment VALUE and opens no connection at
import. Settings are resolved lazily by :func:`get_settings`, and only env-var
NAMES are ever referenced.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# Dotted secret/config NAMES (names only — INVARIANT 4). Single source of truth
# shared by the README and the degraded-reasons report.
ENV_GATEWAY_URL = "clss.teachergrowth.dev.gateway_url"
ENV_EVENT_SINK_URL = "clss.teachergrowth.dev.event_sink_url"
ENV_DATABASE_URL = "clss.teachergrowth.dev.database_url"
ENV_WORKFLOW_URL = "clss.teachergrowth.dev.workflow_url"

_ENV_PREFIX = "CLSS_TEACHERGROWTH_DEV_"

DOTTED_CONVENTION = "clss.<app>.<env>.<purpose>"

# Fixed product invariant, NOT configurable: coaching signals surface to the
# teacher first and are private by default. Employment decisions require a
# separate human review path; this module never produces an open ranking.
COACHING_VISIBILITY = "teacher_first"


def env_var_name(dotted: str) -> str:
    """Map a dotted secret name to its OS environment variable key.

    ``clss.teachergrowth.dev.gateway_url`` -> ``CLSS_TEACHERGROWTH_DEV_GATEWAY_URL``.
    """
    return dotted.replace(".", "_").replace("-", "_").upper()


@dataclass(frozen=True)
class TeacherGrowthSettings:
    """Resolved configuration. Every field is optional; absence -> graceful
    degradation. No secret value is ever defaulted to a literal here
    (INVARIANT 4) — only ``None``.
    """

    env: str = "dev"
    service_name: str = "teacher-growth"

    # Coaching visibility is a product invariant, never an env secret. Surfaced
    # so callers can assert it; it cannot be loosened to a punitive open view.
    coaching_visibility: str = COACHING_VISIBILITY

    # The only egress. Every cross-service call (event store, the A5 workflow
    # engine that routes a quality review to a human, the continuity engine)
    # passes the gateway. Unset -> degraded.
    gateway_url: str | None = None
    # Where emitted coaching-signal events are POSTed (through the gateway).
    # Unset -> events buffer to the in-memory sink.
    event_sink_url: str | None = None
    # The operational store (review records, handover notes). Unset -> in-memory.
    database_url: str | None = None
    # The A5 workflow engine that carries a quality review to a human reviewer
    # for sign-off. Unset -> reviews stay local + pending.
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
    def has_workflow(self) -> bool:
        return bool(self.gateway_url and self.workflow_url)

    @property
    def coaching_is_teacher_first(self) -> bool:
        """Always True — the privacy posture is fixed, not configurable."""
        return self.coaching_visibility == COACHING_VISIBILITY

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
        if not self.workflow_url:
            missing.append(ENV_WORKFLOW_URL)
        return missing


def _read_env(dotted: str) -> str | None:
    value = os.environ.get(env_var_name(dotted))
    if value is None:
        return None
    value = value.strip()
    return value or None


_cached: TeacherGrowthSettings | None = None


def get_settings(*, refresh: bool = False) -> TeacherGrowthSettings:
    """Resolve settings from the environment (by NAME) once, then cache.

    Reads only environment variables — no file, no network, no secret literal.
    Pass ``refresh=True`` to re-read (e.g. after the environment changes in a
    test).
    """
    global _cached
    if _cached is not None and not refresh:
        return _cached
    _cached = TeacherGrowthSettings(
        env=os.environ.get(_ENV_PREFIX + "ENV", "dev"),
        gateway_url=_read_env(ENV_GATEWAY_URL),
        event_sink_url=_read_env(ENV_EVENT_SINK_URL),
        database_url=_read_env(ENV_DATABASE_URL),
        workflow_url=_read_env(ENV_WORKFLOW_URL),
    )
    return _cached
