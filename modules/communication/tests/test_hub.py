"""The hub: messages are always screened, can become routed/owned/tracked tasks,
and cross-context routing is consent-gated."""

from __future__ import annotations

import pytest

from app.config import CommunicationSettings
from app.hub import CommunicationHub, ConsentError, TaskStatus


SENDER = "9999aaaa-0000-4000-8000-00000000000c"
CTX_A = "ctx-thread-a"
CTX_B = "ctx-thread-b"
OWNER = "dddd0000-0000-4000-8000-000000000009"
CONSENT = "cccccccc-0000-4000-8000-000000000003"


def _hub() -> CommunicationHub:
    return CommunicationHub(settings=CommunicationSettings())


def test_every_posted_message_is_screened():
    hub = _hub()
    msg = hub.post(surface="hub", sender_ref=SENDER, context_ref=CTX_A, body="hello team")
    assert msg.finding is not None  # screened on the way in.
    assert msg.is_flagged is False


def test_a_flagged_message_is_admitted_with_an_escalation_not_dropped():
    hub = _hub()
    msg = hub.post(
        surface="hub", sender_ref=SENDER, context_ref=CTX_A,
        body="i want to die",
    )
    assert msg.is_flagged is True
    assert msg.needs_human is True
    # The message is not silently dropped — it is routed to a qualified human.
    assert msg.escalation is not None
    assert msg.escalation.is_crisis is True


def test_a_message_becomes_an_owned_tracked_task():
    hub = _hub()
    msg = hub.post(surface="hub", sender_ref=SENDER, context_ref=CTX_A, body="please send the report")
    task = hub.route_to_task(
        msg, title="Send fortnightly report", owner_role="coordinator",
        owner_ref=OWNER, why="A parent asked for the report.", due_date="2026-06-30",
    )
    assert task.status is TaskStatus.OPEN
    assert task.owner_ref == OWNER
    assert task.from_message_id == msg.message_id
    assert task in hub.tasks()


def test_a_task_requires_a_human_owner():
    hub = _hub()
    msg = hub.post(surface="hub", sender_ref=SENDER, context_ref=CTX_A, body="hi")
    with pytest.raises(ValueError):
        hub.route_to_task(
            msg, title="x", owner_role="coordinator", owner_ref="", why="y",
        )


def test_a_task_is_advanced_only_by_a_human():
    hub = _hub()
    msg = hub.post(surface="hub", sender_ref=SENDER, context_ref=CTX_A, body="hi")
    task = hub.route_to_task(
        msg, title="x", owner_role="coordinator", owner_ref=OWNER, why="y",
    )
    # Advancing/closing is consequential — never auto-fires.
    with pytest.raises(PermissionError):
        task.advance(TaskStatus.DONE, by=None)
    task.advance(TaskStatus.IN_PROGRESS, by=OWNER)
    assert task.status is TaskStatus.IN_PROGRESS


def test_cross_context_routing_without_consent_is_denied():
    hub = _hub()
    msg = hub.post(surface="hub", sender_ref=SENDER, context_ref=CTX_A, body="about the child")
    with pytest.raises(ConsentError):
        hub.route_to_task(
            msg, title="Share with parent", owner_role="teacher", owner_ref=OWNER,
            why="parent partnership", target_context_ref=CTX_B,  # different context.
        )


def test_cross_context_routing_with_consent_is_allowed():
    hub = _hub()
    msg = hub.post(surface="hub", sender_ref=SENDER, context_ref=CTX_A, body="about the child")
    task = hub.route_to_task(
        msg, title="Share with parent", owner_role="teacher", owner_ref=OWNER,
        why="parent partnership", target_context_ref=CTX_B, consent_ref=CONSENT,
    )
    assert task.owner_ref == OWNER


def test_a_safety_flagged_message_carries_its_escalation_onto_the_task():
    hub = _hub()
    msg = hub.post(surface="hub", sender_ref=SENDER, context_ref=CTX_A, body="i want to die")
    task = hub.route_to_task(
        msg, title="Wellbeing follow-up", owner_role="counsellor", owner_ref=OWNER,
        why="A wellbeing signal was detected.",
    )
    assert task.safety_escalation is not None
    assert task.safety_escalation.is_crisis is True
