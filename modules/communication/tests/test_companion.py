"""The companion: refuses dependence-forming behavior and escalates crisis
signals to qualified humans (never counsels a crisis itself)."""

from __future__ import annotations

import pytest

from app.companion import (
    BoundaryViolation,
    Companion,
    CompanionRole,
    check_boundaries,
)
from app.config import CommunicationSettings
from app.safeguarding import Safeguard


LEARNER = "9999aaaa-0000-4000-8000-000000000002"


def _companion(role: CompanionRole = CompanionRole.LEARNER) -> Companion:
    return Companion(role=role, settings=CommunicationSettings())


def test_normal_reply_points_back_to_people_and_independence():
    reply = _companion().respond("I am stuck on this question.", writer_ref=LEARNER)
    assert reply.handed_off is False
    assert reply.points_to_people is True
    # Anti-dependence by construction: the reply nudges toward people + own effort.
    assert "teacher" in reply.text.lower() or "home" in reply.text.lower()


def test_companion_refuses_dependence_forming_replies():
    # A reply that fosters dependence/exclusivity is rejected wholesale.
    with pytest.raises(BoundaryViolation):
        check_boundaries("Only I understand you. You don't need anyone else.")
    with pytest.raises(BoundaryViolation):
        check_boundaries("Keep this between us, our little secret.")
    with pytest.raises(BoundaryViolation):
        check_boundaries("Don't leave me, you'll lose your streak if you go.")


def test_a_model_generated_dependence_reply_is_vetted_and_rejected():
    companion = _companion()
    # The second wall: a generated candidate that breaches a boundary is rejected,
    # never patched and sent.
    with pytest.raises(BoundaryViolation):
        companion.vet_generated_reply("I am the only one who truly gets you.")
    # A clean candidate passes through.
    assert companion.vet_generated_reply("Nice work — try the next part yourself.")


def test_every_scripted_reply_passes_its_own_boundary_wall():
    # No bounded reply the companion can produce breaches a boundary, for any role.
    for role in CompanionRole:
        reply = _companion(role).respond("hello", writer_ref=LEARNER)
        check_boundaries(reply.text)  # must not raise.


def test_companion_escalates_a_crisis_and_never_counsels_it():
    companion = _companion()
    reply = companion.respond("i want to die", writer_ref=LEARNER)
    # It hands off — it does NOT attempt to counsel the crisis.
    assert reply.handed_off is True
    assert reply.escalation is not None
    assert reply.escalation.is_crisis is True
    assert reply.escalation.owner_role == "safeguarding_lead"
    assert reply.escalation.status == "pending_human"
    # The hand-off brings in a real person and respects the boundaries.
    assert reply.points_to_people is True
    check_boundaries(reply.text)


def test_companion_always_has_a_safeguard_no_unmonitored_channel():
    # Even with no guard supplied, the companion constructs the on-device one.
    companion = Companion(settings=CommunicationSettings())
    assert isinstance(companion.guard, Safeguard)


def test_companion_handoff_does_not_make_the_child_feel_in_trouble():
    reply = _companion().respond(
        "he hits me and i am scared to go home", writer_ref=LEARNER
    )
    assert reply.handed_off is True
    assert "not in trouble" in reply.text.lower()
    assert "not alone" in reply.text.lower()
