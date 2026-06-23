"""Connector-health monitoring (spine A6).

Every adapter is a CONNECTOR with an observable health state. This module is the
standards-neutral health model + monitor. It records non-identifying probe
results (latency, ok/fail, a short reason) and derives a state with hysteresis so
a single blip does not flap a connector to DOWN.

NO PII ever enters a health record. Reasons are operational strings only.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Deque

from .models import Standard, utcnow


class HealthState(str, Enum):
    """The lifecycle a connector can be in."""

    UNCONFIGURED = "unconfigured"  # no endpoint/credential route present (DEGRADED)
    HEALTHY = "healthy"            # recent probes succeed
    DEGRADED = "degraded"         # intermittent failures / elevated latency
    DOWN = "down"                 # sustained failures
    UNKNOWN = "unknown"           # no probe yet


@dataclass(frozen=True)
class Probe:
    """A single non-identifying health observation."""

    at: datetime
    ok: bool
    latency_ms: float | None = None
    reason: str | None = None  # operational only, never PII


@dataclass
class ConnectorHealth:
    """Rolling health for one connector (one standard, one tenant connection).

    Hysteresis rules (deterministic, testable):
      - UNCONFIGURED if the connector was never configured (no endpoint route).
      - UNKNOWN until the first probe lands.
      - HEALTHY once the last ``recover_streak`` probes are ok.
      - DOWN once the last ``fail_streak`` probes failed.
      - DEGRADED for any mixed recent window, or elevated latency.
    """

    standard: Standard
    connection_id: str  # opaque tenant-connection id, never PII
    configured: bool = True
    window: int = 10
    fail_streak: int = 3
    recover_streak: int = 2
    latency_budget_ms: float = 2000.0
    probes: Deque[Probe] = field(default_factory=lambda: deque(maxlen=10))

    def __post_init__(self) -> None:
        # Re-bind the deque to honour the configured window size.
        existing = list(self.probes)
        self.probes = deque(existing, maxlen=self.window)

    def record(
        self,
        ok: bool,
        *,
        latency_ms: float | None = None,
        reason: str | None = None,
        at: datetime | None = None,
    ) -> Probe:
        probe = Probe(at=at or utcnow(), ok=ok, latency_ms=latency_ms, reason=reason)
        self.probes.append(probe)
        return probe

    @property
    def last_probe(self) -> Probe | None:
        return self.probes[-1] if self.probes else None

    @property
    def state(self) -> HealthState:
        if not self.configured:
            return HealthState.UNCONFIGURED
        if not self.probes:
            return HealthState.UNKNOWN

        recent = list(self.probes)

        # DOWN — the most recent fail_streak probes all failed.
        tail_fail = recent[-self.fail_streak:]
        if len(tail_fail) >= self.fail_streak and all(not p.ok for p in tail_fail):
            return HealthState.DOWN

        # HEALTHY — the most recent recover_streak probes all ok AND latency ok.
        tail_ok = recent[-self.recover_streak:]
        if len(tail_ok) >= self.recover_streak and all(p.ok for p in tail_ok):
            if all(
                p.latency_ms is None or p.latency_ms <= self.latency_budget_ms
                for p in tail_ok
            ):
                return HealthState.HEALTHY
            return HealthState.DEGRADED

        # Anything mixed/short-but-imperfect is DEGRADED.
        return HealthState.DEGRADED

    def to_safe_dict(self) -> dict:
        last = self.last_probe
        return {
            "standard": self.standard.value,
            "connection_id": self.connection_id,
            "state": self.state.value,
            "configured": self.configured,
            "probe_count": len(self.probes),
            "last_ok": (last.ok if last else None),
            "last_latency_ms": (last.latency_ms if last else None),
            "last_reason": (last.reason if last else None),
        }


class HealthRegistry:
    """A small in-memory registry of connector health for monitoring.

    Production wires probes from real adapter calls (through the gateway). In
    DEGRADED mode unconfigured connectors register as UNCONFIGURED so an
    operator sees exactly which env var NAMES are missing.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, ConnectorHealth] = {}

    def register(self, health: ConnectorHealth) -> ConnectorHealth:
        self._by_id[health.connection_id] = health
        return health

    def get(self, connection_id: str) -> ConnectorHealth | None:
        return self._by_id.get(connection_id)

    def record(
        self,
        connection_id: str,
        ok: bool,
        *,
        latency_ms: float | None = None,
        reason: str | None = None,
    ) -> ConnectorHealth | None:
        health = self._by_id.get(connection_id)
        if health is None:
            return None
        health.record(ok, latency_ms=latency_ms, reason=reason)
        return health

    def summary(self) -> list[dict]:
        return [h.to_safe_dict() for h in self._by_id.values()]

    def any_down(self) -> bool:
        return any(h.state is HealthState.DOWN for h in self._by_id.values())
