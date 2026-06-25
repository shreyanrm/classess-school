"""ProfilingCap gateway registration — the routing.py + policy.py half of the
§1 onboarding circuit ``identity -> gateway -> capability -> event``.

The consent + age-tier-gated implicit-profiling capability is reachable end to
end through the governed routing surface:

  * routing.py: INFER + HINTS are in the ROUTE_MAP (routable), and both are
    cross-context reads of behavioural signals so a PURPOSE is required
    (INVARIANT 6).
  * policy.py: both have an explicit RBAC rule admitting ANY role (a LEARNER
    drives their OWN onboarding profiling — account creation begins with the
    learner), purpose-gated to the account / personalization purposes, and
    scope-checked (ABAC). Deny-by-default holds for an unmapped op and an
    out-of-scope request.

No network/DB — the PolicyEngine and the route table are evaluated directly.
The inference DEPTH bound by the consent + age tier (DPDP) is the MODULE's law
(tested in modules/personalization/tests + backend/tests); this file proves the
GATEWAY door in front of it is wired and deny-by-default.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.policy import PolicyEngine
from app.models import Membership, VerifiedIdentity
from app.routing import lookup

OPERATIONS = [
    ("personalization", "infer", "/personalization/infer"),
    ("personalization", "hints", "/personalization/hints"),
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


@pytest.mark.parametrize("capability,operation,path", OPERATIONS)
def test_profiling_op_is_routable_and_purpose_required(capability, operation, path):
    route = lookup(capability, operation)
    assert route is not None, f"{capability}.{operation} not in ROUTE_MAP (not routable)"
    assert route.method == "POST"
    assert route.path == path
    # A cross-context read of behavioural signals -> a purpose must be asserted.
    assert route.purpose_required is True


# --- RBAC: any role admits with the account purpose (the learner included) -- #


@pytest.mark.parametrize("capability,operation,_path", OPERATIONS)
@pytest.mark.parametrize("role", ["student", "parent", "teacher", "admin"])
def test_profiling_admits_any_role_with_account_purpose(engine, capability, operation, _path, role):
    decision = engine.evaluate(
        identity=_identity(role),
        capability=capability,
        operation=operation,
        resource_scope="inst-1",
        purpose="account",
    )
    assert decision.decision == "allow", decision.reasons


# --- purpose gate: a missing / wrong purpose is denied (INVARIANT 6) -------- #


@pytest.mark.parametrize("capability,operation,_path", OPERATIONS)
def test_profiling_denies_without_a_permitted_purpose(engine, capability, operation, _path):
    decision = engine.evaluate(
        identity=_identity("student"),
        capability=capability,
        operation=operation,
        resource_scope="inst-1",
        purpose=None,  # no purpose asserted
    )
    assert decision.decision == "deny"

    wrong = engine.evaluate(
        identity=_identity("student"),
        capability=capability,
        operation=operation,
        resource_scope="inst-1",
        purpose="assessment",  # not a personalization purpose
    )
    assert wrong.decision == "deny"


# --- ABAC: cannot reach outside a covered institution scope ----------------- #


@pytest.mark.parametrize("capability,operation,_path", OPERATIONS)
def test_profiling_denies_cross_institution_scope(engine, capability, operation, _path):
    decision = engine.evaluate(
        identity=_identity("student", scope="inst-1"),
        capability=capability,
        operation=operation,
        resource_scope="inst-OTHER",  # not covered by the membership
        purpose="account",
    )
    assert decision.decision == "deny"


# --- deny-by-default for an unmapped personalization op --------------------- #


def test_unmapped_profiling_op_denied_by_default(engine):
    decision = engine.evaluate(
        identity=_identity("student"),
        capability="personalization",
        operation="exfiltrate",  # no rule registered
        resource_scope="inst-1",
        purpose="account",
    )
    assert decision.decision == "deny"
    assert any("deny by default" in r for r in decision.reasons)
