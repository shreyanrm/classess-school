"""The AI control centre (spine A7).

The single pane over the AI fabric's behavior, and the emergency brake:

- **Model usage** — ingest usage samples and report counts, served/withheld
  rates, and latency per capability and per tier.
- **Track 1 / Track 2 view** (INVARIANT 11) — usage is reported with the two
  tracks STRICTLY SEPARATE. ``track_view`` returns a dict keyed by track; the
  totals are never collapsed into one cross-track figure, and an unknown track
  number is rejected rather than silently folded in.
- **Confidence-gate stats** (INVARIANT 7) — the served vs withheld counts and
  the mean confidence of served content, so an operator can see whether the gate
  is doing its job.
- **Emergency disable** — a kill switch. ``emergency_disable`` halts a
  capability immediately; ``is_enabled`` then reports it off, and a guarded
  caller routes through ``guard`` which raises ``CapabilityDisabledError`` so a
  disabled capability genuinely cannot run. Re-enable requires a separate call.

Every disable / enable is recorded immutably through the audit log: an emergency
stop is itself a privileged, reviewable action.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from .audit import AuditLog
from .models import CapabilityState, ModelUsageSample

_VALID_TRACKS = (1, 2)


class CapabilityDisabledError(RuntimeError):
    """Raised when a guarded call targets an emergency-disabled capability."""


class UnknownTrackError(ValueError):
    """Raised when a usage sample names a track other than 1 or 2 (INVARIANT 11)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ControlCentre:
    def __init__(self, audit_log: AuditLog) -> None:
        self._audit = audit_log
        self._usage: list[ModelUsageSample] = []
        self._states: dict[str, CapabilityState] = {}

    # -- usage ingest -------------------------------------------------------
    def ingest(self, sample: ModelUsageSample) -> None:
        if sample.track not in _VALID_TRACKS:
            # INVARIANT 11: there are exactly two tracks; nothing else exists.
            raise UnknownTrackError(
                f"usage track must be 1 (external) or 2 (proprietary/edge), got {sample.track!r}"
            )
        self._usage.append(sample)

    # -- usage reporting ----------------------------------------------------
    def usage_by_capability(self) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for s in self._usage:
            row = out.setdefault(
                s.capability,
                {"calls": 0, "served": 0, "withheld": 0, "latency_ms_total": 0},
            )
            row["calls"] += 1
            row["served"] += 1 if s.served else 0
            row["withheld"] += 0 if s.served else 1
            row["latency_ms_total"] += s.latency_ms
        for row in out.values():
            calls = row["calls"] or 1
            row["mean_latency_ms"] = row["latency_ms_total"] / calls
        return out

    def track_view(self) -> dict[int, dict[str, float]]:
        """Track 1 and Track 2 reported SEPARATELY (INVARIANT 11).

        Returns a dict keyed by track number. There is deliberately no combined
        total — the two tracks are never conflated into a single figure.
        """
        view: dict[int, dict[str, float]] = {1: _empty_track(), 2: _empty_track()}
        for s in self._usage:
            row = view[s.track]
            row["calls"] += 1
            row["served"] += 1 if s.served else 0
        return view

    def confidence_gate_stats(self, capability: str | None = None) -> dict[str, float]:
        """Served vs withheld + mean confidence of served content (INVARIANT 7)."""
        samples = [
            s for s in self._usage
            if capability is None or s.capability == capability
        ]
        served = [s for s in samples if s.served]
        withheld = [s for s in samples if not s.served]
        total = len(samples)
        mean_served_conf = (
            sum(s.confidence for s in served) / len(served) if served else 0.0
        )
        return {
            "total": total,
            "served": len(served),
            "withheld": len(withheld),
            "served_rate": (len(served) / total) if total else 0.0,
            "mean_served_confidence": mean_served_conf,
        }

    # -- emergency disable / enable ----------------------------------------
    def is_enabled(self, capability: str) -> bool:
        state = self._states.get(capability)
        # Default-enabled: a capability with no recorded state is live.
        return True if state is None else state.enabled

    async def emergency_disable(
        self, *, capability: str, reason: str, actor_uuid: UUID, tenant_id: UUID
    ) -> CapabilityState:
        if not str(reason or "").strip():
            raise ValueError("emergency_disable requires a reason.")
        state = CapabilityState(
            capability=capability,
            enabled=False,
            disabled_reason=reason.strip(),
            disabled_by=actor_uuid,
            changed_at=_now(),
        )
        self._states[capability] = state
        await self._audit.record(
            actor_uuid=actor_uuid,
            action="control_centre.emergency_disable",
            resource=capability,
            purpose="governance",
            tenant_id=tenant_id,
            privileged=True,
            detail={"reason": state.disabled_reason},
        )
        return state

    async def enable(
        self, *, capability: str, actor_uuid: UUID, tenant_id: UUID
    ) -> CapabilityState:
        state = CapabilityState(
            capability=capability, enabled=True,
            disabled_reason=None, disabled_by=actor_uuid, changed_at=_now(),
        )
        self._states[capability] = state
        await self._audit.record(
            actor_uuid=actor_uuid,
            action="control_centre.enable",
            resource=capability,
            purpose="governance",
            tenant_id=tenant_id,
            privileged=True,
            detail={},
        )
        return state

    def guard(self, capability: str) -> None:
        """Call before invoking a capability; raises if it is disabled.

        This is the enforcement seam: a halted capability genuinely cannot run
        because every governed call site routes through ``guard`` first.
        """
        if not self.is_enabled(capability):
            state = self._states.get(capability)
            reason = state.disabled_reason if state else "disabled"
            raise CapabilityDisabledError(
                f"capability {capability!r} is emergency-disabled: {reason}"
            )


def _empty_track() -> dict[str, float]:
    return {"calls": 0, "served": 0}
