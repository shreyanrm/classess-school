"""Audit log: append + read only, immutable, queryable. No network/DB.

INVARIANT 9 — audit is immutable. Async service methods are driven with
``asyncio.run`` so the suite needs no pytest-asyncio plugin.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from app.audit import InMemoryAuditLog, build_audit_log
from app.models import AuditQuery, new_id


def _log() -> InMemoryAuditLog:
    return InMemoryAuditLog()


def test_record_then_query_roundtrip():
    log = _log()
    actor, tenant = new_id(), new_id()
    rec = asyncio.run(
        log.record(
            actor_uuid=actor, action="audit.test", resource="r1",
            purpose="governance", tenant_id=tenant, detail={"k": "v"},
        )
    )
    assert rec.action == "audit.test"
    found = asyncio.run(log.query(AuditQuery(actor_uuid=actor)))
    assert len(found) == 1
    assert found[0].audit_id == rec.audit_id
    assert found[0].detail == {"k": "v"}


def test_query_filters_by_action_resource_tenant_and_privileged():
    log = _log()
    a, t = new_id(), new_id()
    asyncio.run(log.record(actor_uuid=a, action="open", resource="cap.x",
                           purpose="p", tenant_id=t, privileged=True))
    asyncio.run(log.record(actor_uuid=a, action="read", resource="cap.y",
                           purpose="p", tenant_id=t, privileged=False))
    assert len(asyncio.run(log.query(AuditQuery(action="open")))) == 1
    assert len(asyncio.run(log.query(AuditQuery(resource="cap.y")))) == 1
    assert len(asyncio.run(log.query(AuditQuery(tenant_id=t)))) == 2
    privileged = asyncio.run(log.query(AuditQuery(privileged_only=True)))
    assert len(privileged) == 1 and privileged[0].action == "open"


def test_query_time_window():
    log = _log()
    a, t = new_id(), new_id()
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    asyncio.run(log.record(actor_uuid=a, action="x", resource="r", purpose="p",
                           tenant_id=t, occurred_at=base))
    asyncio.run(log.record(actor_uuid=a, action="x", resource="r", purpose="p",
                           tenant_id=t, occurred_at=base + timedelta(days=5)))
    out = asyncio.run(log.query(AuditQuery(since=base + timedelta(days=1))))
    assert len(out) == 1


def test_audit_is_immutable_no_mutation_surface():
    # There is no update/delete method on the audit log at all.
    log = _log()
    assert not hasattr(log, "update")
    assert not hasattr(log, "delete")
    a, t = new_id(), new_id()
    asyncio.run(log.record(actor_uuid=a, action="x", resource="r",
                           purpose="p", tenant_id=t))
    # Mutating a returned record / list must not change the ledger.
    out = asyncio.run(log.query(AuditQuery()))
    out.clear()
    assert len(asyncio.run(log.query(AuditQuery()))) == 1


def test_returned_records_are_frozen():
    log = _log()
    a, t = new_id(), new_id()
    rec = asyncio.run(log.record(actor_uuid=a, action="x", resource="r",
                                 purpose="p", tenant_id=t))
    import dataclasses
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.action = "tampered"  # type: ignore[misc]


def test_build_audit_log_degrades_to_memory_without_db():
    assert isinstance(build_audit_log(None), InMemoryAuditLog)
