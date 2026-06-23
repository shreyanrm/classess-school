"""The connector framework (spine A6).

Every adapter is a ``Connector``: a uniform interface over one standard. The
framework gives each connector:

  - a ``standard`` and an opaque ``connection_id`` (tenant connection, no PII),
  - a ``ConnectorHealth`` it reports into,
  - a ``capabilities()`` declaration (what the connector can do),
  - a ``configured`` flag derived from whether its route NAME is present,
  - a ``probe()`` hook that records a health observation.

Connectors hold NO credentials. Any outbound call is described and handed to a
governed capability behind the gateway; the connector itself only parses,
validates, and maps. This makes every adapter interface-complete and fully
exercisable with no live endpoint (DEGRADED mode).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .health import ConnectorHealth, HealthState
from .models import Standard


class Direction(str, Enum):
    INBOUND = "inbound"     # external -> Classess (e.g. roster import)
    OUTBOUND = "outbound"   # Classess -> external (e.g. grade passback)
    BIDIRECTIONAL = "bidirectional"


@dataclass(frozen=True)
class Capability:
    """A declared connector capability (a verb the connector supports)."""

    name: str
    direction: Direction
    description: str
    # Whether invoking it is a CONSEQUENTIAL action (writes/sends to an external
    # system) — those require the permission ladder + human approval upstream
    # (INVARIANT 8); the connector never auto-fires them.
    consequential: bool = False


class Connector:
    """Base class for every standards adapter.

    Subclasses set ``standard`` and implement ``capabilities()``. The base owns
    the health object and the configured/degraded reporting so monitoring is
    uniform across LTI, OneRoster, xAPI, QTI, SCORM, Clever/ClassLink, Ed-Fi,
    CASE and MCP.
    """

    standard: Standard

    def __init__(
        self,
        connection_id: str,
        *,
        endpoint_route: str | None = None,
    ) -> None:
        if not connection_id:
            raise ValueError("connection_id is required (opaque, never PII).")
        self.connection_id = connection_id
        # ``endpoint_route`` is a NAME of a gateway route or env var — never a
        # secret value. Its presence flips the connector out of UNCONFIGURED.
        self.endpoint_route = endpoint_route
        self.health = ConnectorHealth(
            standard=self.standard,
            connection_id=connection_id,
            configured=bool(endpoint_route),
        )

    # -- declaration --------------------------------------------------------
    def capabilities(self) -> list[Capability]:  # pragma: no cover - overridden
        raise NotImplementedError

    @property
    def configured(self) -> bool:
        return self.health.configured

    @property
    def degraded(self) -> bool:
        """A connector is degraded when it has no live endpoint route."""

        return not self.configured

    # -- health -------------------------------------------------------------
    def probe(
        self,
        ok: bool,
        *,
        latency_ms: float | None = None,
        reason: str | None = None,
    ) -> HealthState:
        """Record a probe and return the resulting health state."""

        self.health.record(ok, latency_ms=latency_ms, reason=reason)
        return self.health.state

    @property
    def state(self) -> HealthState:
        return self.health.state

    def to_safe_dict(self) -> dict:
        return {
            "standard": self.standard.value,
            "connection_id": self.connection_id,
            "configured": self.configured,
            "degraded": self.degraded,
            "state": self.state.value,
            "capabilities": [
                {
                    "name": c.name,
                    "direction": c.direction.value,
                    "consequential": c.consequential,
                }
                for c in self.capabilities()
            ],
        }
