"""Child-safety: crisis escalates, moderation flags, no unmonitored channel.

INVARIANT 12 / A7. No network/DB — the default deterministic classifier runs
in-process.
"""

from __future__ import annotations

import asyncio

import pytest

from app.audit import InMemoryAuditLog
from app.child_safety import ChildSafetySubsystem, UnmonitoredChannelError
from app.models import AuditQuery, EscalationStatus, SafetyVerdict, new_id


def _sub():
    audit = InMemoryAuditLog()
    return ChildSafetySubsystem(audit), audit


def test_unmonitored_surface_refuses_free_text():
    sub, _ = _sub()
    with pytest.raises(UnmonitoredChannelError):
        asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                               text="hello", tenant_id=new_id()))


def test_monitored_surface_allows_benign_text():
    sub, _ = _sub()
    sub.register_surface("companion.chat")
    a = asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                               text="can you help me with fractions please",
                               tenant_id=new_id()))
    assert a.verdict is SafetyVerdict.ALLOW
    assert a.monitored is True
    assert a.crisis is False


def test_moderation_flags_harassment():
    sub, _ = _sub()
    sub.register_surface("class.discussion")
    a = asyncio.run(sub.assess(surface="class.discussion", canonical_uuid=new_id(),
                               text="you are such an idiot", tenant_id=new_id()))
    assert a.verdict in (SafetyVerdict.FLAG, SafetyVerdict.BLOCK)
    assert "harassment" in a.categories


def test_crisis_detected_escalates_to_a_human():
    sub, audit = _sub()
    sub.register_surface("companion.chat")
    tenant = new_id()
    a = asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                               text="sometimes i want to kill myself",
                               tenant_id=tenant))
    assert a.crisis is True
    assert a.verdict is SafetyVerdict.CRISIS
    # An escalation was raised to a qualified human.
    pending = sub.pending_escalations()
    assert len(pending) == 1
    assert pending[0].status is EscalationStatus.PENDING
    # And it was recorded immutably as a privileged audit entry.
    esc_audit = asyncio.run(audit.query(AuditQuery(action="child_safety.escalate")))
    assert len(esc_audit) == 1 and esc_audit[0].privileged is True


def test_crisis_overrides_moderation_verdict():
    sub, _ = _sub()
    sub.register_surface("companion.chat")
    # Contains both an insult and a crisis signal: crisis wins.
    a = asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                               text="you idiot, i want to die", tenant_id=new_id()))
    assert a.verdict is SafetyVerdict.CRISIS


def test_escalation_can_be_acknowledged_by_a_handler():
    sub, audit = _sub()
    sub.register_surface("companion.chat")
    tenant = new_id()
    asyncio.run(sub.assess(surface="companion.chat", canonical_uuid=new_id(),
                           text="i want to die", tenant_id=tenant))
    esc = sub.pending_escalations()[0]
    handler = new_id()
    ack = asyncio.run(sub.acknowledge(escalation_id=esc.escalation_id,
                                      handler_uuid=handler, tenant_id=tenant,
                                      note="counsellor notified"))
    assert ack.status is EscalationStatus.ACKNOWLEDGED
    assert sub.pending_escalations() == []
    assert len(asyncio.run(
        audit.query(AuditQuery(action="child_safety.escalation_acknowledged")))) == 1


def test_default_classifier_abstains_rather_than_asserting_safe():
    # An ambiguous, non-matching string returns low confidence (not verified
    # safe) so the caller can route it to review (INVARIANT 7 fail-toward-review).
    from app.child_safety import DeterministicSafetyClassifier

    cats, crisis, conf = DeterministicSafetyClassifier().classify("the weather today")
    assert crisis is False and cats == ()
    assert conf < 0.5
