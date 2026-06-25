"""The generate-and-verify GENERATORS are reachable end to end through the
governed routing surface: each is in the ROUTE_MAP (routable) AND has an explicit
RBAC rule (teacher/admin allowed; deny-by-default otherwise).

This is the routing.py + policy.py half of the circuit
``identity -> gateway -> capability -> event``. No network/DB — the PolicyEngine
and the route table are evaluated directly.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.policy import PolicyEngine
from app.models import Membership, VerifiedIdentity
from app.routing import lookup

# The four named generators + the generate-and-verify content door (lesson
# visuals ride this one with kind=lesson_visual).
GENERATORS = [
    ("content", "generate-worksheet", "/content/generate_worksheet"),
    ("content", "generate-and-verify-content", "/content/generate_and_verify_content"),
    ("planning", "generate-course-outline", "/planning/generate_course_outline"),
    ("planning", "generate-lesson-plan", "/planning/generate_lesson_plan"),
    ("planning", "generate-session-plan", "/planning/generate_session_plan"),
]


def _identity(role: str, *, scope: str = "inst-1") -> VerifiedIdentity:
    return VerifiedIdentity(
        canonical_uuid=uuid4(),
        app="school",
        memberships=[
            Membership(app="school", role=role, scope=scope, granted_at=datetime.now(timezone.utc))
        ],
    )


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine.baseline()


# --- routability (routing.py ROUTE_MAP) ------------------------------------- #


@pytest.mark.parametrize("capability,operation,path", GENERATORS)
def test_generator_is_routable(capability, operation, path):
    """Each generator operationId resolves to an upstream route — without a
    ROUTE_MAP entry the gateway returns 'not routable' (deny-by-default)."""
    route = lookup(capability, operation)
    assert route is not None, f"{capability}.{operation} not in ROUTE_MAP (not routable)"
    assert route.method == "POST"
    assert route.path == path
    # A prepare/generate, NOT a cross-context read: no purpose assertion gate.
    assert route.purpose_required is False


# --- RBAC: teacher + admin admit (policy.py) -------------------------------- #


@pytest.mark.parametrize("capability,operation,_path", GENERATORS)
@pytest.mark.parametrize("role", ["teacher", "admin"])
def test_generator_admits_for_staff(engine, capability, operation, _path, role):
    decision = engine.evaluate(
        identity=_identity(role),
        capability=capability,
        operation=operation,
        resource_scope="inst-1",  # within the caller's membership scope
        purpose=None,
    )
    assert decision.decision == "allow", decision.reasons


# --- RBAC: unauthorized roles denied (deny-by-default) ---------------------- #


@pytest.mark.parametrize("capability,operation,_path", GENERATORS)
@pytest.mark.parametrize("role", ["student", "parent"])
def test_generator_denies_non_staff(engine, capability, operation, _path, role):
    decision = engine.evaluate(
        identity=_identity(role),
        capability=capability,
        operation=operation,
        resource_scope="inst-1",
        purpose=None,
    )
    assert decision.decision == "deny"


# --- ABAC: a teacher cannot reach outside a covered institution scope ------- #


@pytest.mark.parametrize("capability,operation,_path", GENERATORS)
def test_generator_denies_cross_institution_scope(engine, capability, operation, _path):
    decision = engine.evaluate(
        identity=_identity("teacher", scope="inst-1"),
        capability=capability,
        operation=operation,
        resource_scope="inst-OTHER",  # not covered by the membership
        purpose=None,
    )
    assert decision.decision == "deny"


# --- deny-by-default for an unmapped generator op --------------------------- #


def test_unmapped_generator_op_denied_by_default(engine):
    decision = engine.evaluate(
        identity=_identity("teacher"),
        capability="planning",
        operation="generate-ghost-plan",  # no rule registered
        resource_scope="inst-1",
        purpose=None,
    )
    assert decision.decision == "deny"
    assert any("deny by default" in r for r in decision.reasons)
