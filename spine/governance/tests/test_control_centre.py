"""Control centre: track separation, gate stats, emergency disable. No network/DB.

INVARIANTS 7 + 11.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.audit import InMemoryAuditLog
from app.control_centre import (
    CapabilityDisabledError,
    ControlCentre,
    UnknownTrackError,
)
from app.models import AuditQuery, ModelUsageSample, new_id


def _cc():
    return ControlCentre(InMemoryAuditLog())


def _sample(track=1, served=True, conf=0.9, cap="explain.step", tier="mid", lat=120):
    return ModelUsageSample(
        capability=cap, track=track, tier=tier, served=served,
        confidence=conf, latency_ms=lat, occurred_at=datetime.now(timezone.utc),
    )


def test_track1_and_track2_reported_separately():
    cc = _cc()
    cc.ingest(_sample(track=1, served=True))
    cc.ingest(_sample(track=1, served=False))
    cc.ingest(_sample(track=2, served=True))
    view = cc.track_view()
    # Two distinct buckets, never summed into one cross-track figure.
    assert set(view.keys()) == {1, 2}
    assert view[1]["calls"] == 2 and view[1]["served"] == 1
    assert view[2]["calls"] == 1 and view[2]["served"] == 1


def test_unknown_track_is_rejected():
    cc = _cc()
    with pytest.raises(UnknownTrackError):
        cc.ingest(_sample(track=3))


def test_confidence_gate_stats():
    cc = _cc()
    cc.ingest(_sample(served=True, conf=0.9))
    cc.ingest(_sample(served=True, conf=0.8))
    cc.ingest(_sample(served=False, conf=0.2))
    stats = cc.confidence_gate_stats()
    assert stats["total"] == 3
    assert stats["served"] == 2
    assert stats["withheld"] == 1
    assert abs(stats["served_rate"] - (2 / 3)) < 1e-9
    assert abs(stats["mean_served_confidence"] - 0.85) < 1e-9


def test_usage_by_capability_mean_latency():
    cc = _cc()
    cc.ingest(_sample(cap="evaluate.response", lat=100))
    cc.ingest(_sample(cap="evaluate.response", lat=300))
    row = cc.usage_by_capability()["evaluate.response"]
    assert row["calls"] == 2
    assert row["mean_latency_ms"] == 200


def test_emergency_disable_halts_a_capability():
    cc = _cc()
    cap = "content.generate-practice-item"
    assert cc.is_enabled(cap) is True
    cc.guard(cap)  # enabled -> no raise
    asyncio.run(cc.emergency_disable(capability=cap, reason="provider incident",
                                     actor_uuid=new_id(), tenant_id=new_id()))
    assert cc.is_enabled(cap) is False
    with pytest.raises(CapabilityDisabledError):
        cc.guard(cap)  # disabled -> a guarded call cannot run


def test_emergency_disable_requires_reason_and_is_audited():
    cc = _cc()
    with pytest.raises(ValueError):
        asyncio.run(cc.emergency_disable(capability="cap.x", reason="  ",
                                         actor_uuid=new_id(), tenant_id=new_id()))
    audit = cc._audit  # the same in-memory log
    asyncio.run(cc.emergency_disable(capability="cap.x", reason="halt now",
                                     actor_uuid=new_id(), tenant_id=new_id()))
    entries = asyncio.run(audit.query(AuditQuery(action="control_centre.emergency_disable")))
    assert len(entries) == 1 and entries[0].privileged is True


def test_re_enable_restores_capability():
    cc = _cc()
    cap = "cap.x"
    asyncio.run(cc.emergency_disable(capability=cap, reason="r",
                                     actor_uuid=new_id(), tenant_id=new_id()))
    assert cc.is_enabled(cap) is False
    asyncio.run(cc.enable(capability=cap, actor_uuid=new_id(), tenant_id=new_id()))
    assert cc.is_enabled(cap) is True
    cc.guard(cap)  # no raise
