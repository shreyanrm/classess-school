"""The companion is role-shaped into student/teacher/parent/admin over one
identity — tone differs, boundaries are identical across every shape."""

from __future__ import annotations

from app.companion import Companion, CompanionRole, check_boundaries
from app.config import CommunicationSettings


USER = "9999aaaa-0000-4000-8000-000000000030"

FUNCTIONAL = (
    CompanionRole.STUDENT,
    CompanionRole.TEACHER,
    CompanionRole.PARENT,
    CompanionRole.ADMIN,
)


def _companion(role: CompanionRole) -> Companion:
    return Companion(role=role, settings=CommunicationSettings())


def test_every_functional_role_replies_within_the_boundaries():
    for role in FUNCTIONAL:
        reply = _companion(role).respond("help me", writer_ref=USER)
        check_boundaries(reply.text)  # identical boundaries for every shape.
        assert reply.role is role


def test_staff_roles_frame_as_prepare_and_human_decides():
    for role in (CompanionRole.TEACHER, CompanionRole.ADMIN):
        reply = _companion(role).respond("draft this", writer_ref=USER)
        # Permission ladder shape: the companion prepares; the human decides.
        assert "prepare" in reply.text.lower()
        assert "you" in reply.text.lower()


def test_student_role_still_points_to_independence_and_people():
    reply = _companion(CompanionRole.STUDENT).respond("I am stuck", writer_ref=USER)
    assert reply.points_to_people is True
    assert "yourself" in reply.text.lower()


def test_crisis_escalates_identically_regardless_of_role_shape():
    for role in FUNCTIONAL:
        reply = _companion(role).respond("i want to die", writer_ref=USER)
        assert reply.handed_off is True
        assert reply.escalation is not None
        assert reply.escalation.is_crisis is True
