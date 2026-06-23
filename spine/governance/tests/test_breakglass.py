"""Break-glass: demands a reason, records immutably, reviewable. No network/DB.

INVARIANT 9.
"""

from __future__ import annotations

import asyncio

import pytest

from app.audit import InMemoryAuditLog
from app.breakglass import (
    ApprovalRequiredError,
    BreakGlassService,
    ReasonRequiredError,
)
from app.models import AuditQuery, new_id


def _svc(**kw):
    audit = InMemoryAuditLog()
    return BreakGlassService(audit, **kw), audit


def test_open_requires_a_reason():
    svc, _ = _svc()
    for bad in ("", "   ", None):
        with pytest.raises(ReasonRequiredError):
            asyncio.run(svc.open(actor_uuid=new_id(), capability="cap.admin",
                                 reason=bad, tenant_id=new_id()))  # type: ignore[arg-type]


def test_open_with_reason_records_immutable_privileged_audit():
    svc, audit = _svc()
    actor, tenant = new_id(), new_id()
    grant = asyncio.run(svc.open(actor_uuid=actor, capability="cap.admin",
                                 reason="incident 42 — locked-out principal",
                                 tenant_id=tenant))
    assert grant.reason == "incident 42 — locked-out principal"
    # An immutable, privileged audit entry exists for the open.
    entries = asyncio.run(audit.query(AuditQuery(action="breakglass.open")))
    assert len(entries) == 1
    assert entries[0].privileged is True
    assert entries[0].detail["reason"] == grant.reason
    assert entries[0].detail["grant_id"] == str(grant.grant_id)


def test_grant_is_active_then_reviewable():
    svc, _ = _svc()
    grant = asyncio.run(svc.open(actor_uuid=new_id(), capability="cap.x",
                                 reason="r", tenant_id=new_id()))
    assert svc.is_active(grant.grant_id) is True
    assert grant in svc.list_open()
    assert grant.grant_id in {g.grant_id for g in svc.list_for_review()}


def test_review_records_reviewer_and_audits():
    svc, audit = _svc()
    grant = asyncio.run(svc.open(actor_uuid=new_id(), capability="cap.x",
                                 reason="r", tenant_id=new_id()))
    reviewer = new_id()
    reviewed = asyncio.run(svc.review(grant_id=grant.grant_id,
                                      reviewed_by=reviewer, note="looks legitimate"))
    assert reviewed.reviewed_by == reviewer
    # No longer pending review.
    assert grant.grant_id not in {g.grant_id for g in svc.list_for_review()}
    assert len(asyncio.run(audit.query(AuditQuery(action="breakglass.review")))) == 1


def test_close_deactivates_but_keeps_history():
    svc, audit = _svc()
    grant = asyncio.run(svc.open(actor_uuid=new_id(), capability="cap.x",
                                 reason="r", tenant_id=new_id()))
    asyncio.run(svc.close(grant_id=grant.grant_id, actor_uuid=new_id()))
    assert svc.is_active(grant.grant_id) is False
    assert grant.grant_id not in {g.grant_id for g in svc.list_open()}
    # Original open audit entry is still there (immutable history).
    assert len(asyncio.run(audit.query(AuditQuery(action="breakglass.open")))) == 1
    assert len(asyncio.run(audit.query(AuditQuery(action="breakglass.close")))) == 1


def test_four_eyes_capability_needs_an_approver():
    svc, _ = _svc(require_approval_for=frozenset({"cap.delete-tenant"}))
    with pytest.raises(ApprovalRequiredError):
        asyncio.run(svc.open(actor_uuid=new_id(), capability="cap.delete-tenant",
                             reason="r", tenant_id=new_id()))
    # With an approver it opens.
    grant = asyncio.run(svc.open(actor_uuid=new_id(), capability="cap.delete-tenant",
                                 reason="r", tenant_id=new_id(), approved_by=new_id()))
    assert grant.approved_by is not None


def test_expired_grant_is_not_active():
    svc, _ = _svc(ttl_seconds=0)
    grant = asyncio.run(svc.open(actor_uuid=new_id(), capability="cap.x",
                                 reason="r", tenant_id=new_id()))
    # TTL 0 -> expires_at == opened_at, so it is not active a moment later.
    assert svc.is_active(grant.grant_id) is False
