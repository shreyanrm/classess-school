"""The wall: a feature-module route is unreachable without a valid token + a
satisfied policy, and every decision is audited.

No network/DB. All collaborators are fakes.
"""

import pytest

from app.capabilities import (
    Action,
    DenyReason,
    Principal,
    WallDenied,
    build_default_registry,
)
from app.ratelimit import RateLimitRule, RateLimiter
from app.wall import (
    InMemoryAuditSink,
    Wall,
)


# --- fakes ------------------------------------------------------------------ #


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class FakeVerifier:
    def __init__(self, principals):
        # token -> Principal
        self._p = principals

    def verify(self, token):
        return self._p.get(token)


class FakeConsent:
    def has_consent(self, principal, scope):
        return scope in principal.consent_scopes


class AllowAllChildSafety:
    def is_safe(self, text):
        return True


class BlockWordChildSafety:
    def is_safe(self, text):
        return "blocked" not in text.lower()


# --- fixtures --------------------------------------------------------------- #


def make_wall(**overrides):
    registry = build_default_registry()
    limiter = RateLimiter(
        default_rule=RateLimitRule(limit=1000, window_seconds=60),
        clock=FakeClock(),
    )
    audit = InMemoryAuditSink()
    teacher = Principal(
        canonical_uuid="uuid-teacher",
        roles=("teacher",),
        institution_uuid="inst-1",
        consent_scopes=("learning.read",),
    )
    admin = Principal(
        canonical_uuid="uuid-admin",
        roles=("admin",),
        institution_uuid="inst-1",
        consent_scopes=("feature-store.read", "intelligence-views.read"),
    )
    learner = Principal(
        canonical_uuid="uuid-learner", roles=("learner",), institution_uuid="inst-1"
    )
    verifier = FakeVerifier({"tok-teacher": teacher, "tok-admin": admin, "tok-learner": learner})
    kwargs = dict(
        registry=registry,
        limiter=limiter,
        verifier=verifier,
        consent=FakeConsent(),
        child_safety=AllowAllChildSafety(),
        audit=audit,
        clock=FakeClock(),
    )
    kwargs.update(overrides)
    return Wall(**kwargs), audit


# --- registration coverage -------------------------------------------------- #

EXPECTED_MODULES = {
    "institution", "scheduling", "coursework", "learning", "content",
    "learner-record", "communication", "intelligence-views", "attendance",
    "planning", "classroom", "teacher-growth", "integration", "feature-store",
    # The governance control plane (GAP#3/#5/#7): the audit-trail READ + the
    # consequential AI-control toggle / break-glass / policy-version EXECUTE rung.
    "governance",
}


def test_all_feature_modules_registered_as_capabilities():
    reg = build_default_registry()
    assert set(reg.modules()) == EXPECTED_MODULES
    # every module is at least readable behind the wall.
    for m in EXPECTED_MODULES:
        assert reg.has(f"{m}.read")


# --- token / authn ---------------------------------------------------------- #


def test_route_unreachable_without_token():
    wall, audit = make_wall()
    with pytest.raises(WallDenied) as ei:
        wall.admit(route="learning.read", token=None, payload={"subject_uuid": "u1"})
    assert ei.value.reason is DenyReason.NO_TOKEN
    assert audit.events[-1].allowed is False
    assert audit.events[-1].reason == "no_token"


def test_route_unreachable_with_invalid_token():
    wall, audit = make_wall()
    with pytest.raises(WallDenied) as ei:
        wall.admit(route="learning.read", token="garbage", payload={"subject_uuid": "u1"})
    assert ei.value.reason is DenyReason.INVALID_TOKEN
    assert audit.events[-1].reason == "invalid_token"


def test_unknown_route_fails_closed():
    wall, audit = make_wall()
    with pytest.raises(WallDenied) as ei:
        wall.admit(route="ghost.read", token="tok-admin")
    assert ei.value.reason is DenyReason.UNKNOWN_ROUTE


# --- happy path ------------------------------------------------------------- #


def test_valid_token_and_policy_admits_and_audits_allow():
    wall, audit = make_wall()
    result = wall.admit(
        route="learning.read",
        token="tok-teacher",
        payload={"subject_uuid": "u1"},
        attributes={"institution_uuid": "inst-1"},
    )
    assert result.allowed is True
    assert result.capability.route == "learning.read"
    assert audit.events[-1].allowed is True
    assert audit.events[-1].reason is None
    assert audit.events[-1].actor_uuid == "uuid-teacher"


# --- schema validation at the wall ----------------------------------------- #


def test_malformed_request_rejected_before_routing():
    wall, audit = make_wall()
    with pytest.raises(WallDenied) as ei:
        # missing required subject_uuid, plus an unknown field
        wall.admit(
            route="learning.read",
            token="tok-teacher",
            payload={"injected": "x"},
            attributes={"institution_uuid": "inst-1"},
        )
    assert ei.value.reason is DenyReason.SCHEMA_INVALID
    assert audit.events[-1].reason == "schema_invalid"


# --- RBAC ------------------------------------------------------------------- #


def test_rbac_denies_role_without_permission():
    wall, audit = make_wall()
    # learner cannot WRITE to learning.
    with pytest.raises(WallDenied) as ei:
        wall.admit(
            route="learning.write",
            token="tok-learner",
            payload={"subject_uuid": "u1"},
            attributes={"institution_uuid": "inst-1"},
        )
    assert ei.value.reason is DenyReason.RBAC_DENIED


# --- ABAC ------------------------------------------------------------------- #


def test_abac_denies_cross_institution():
    wall, audit = make_wall()
    with pytest.raises(WallDenied) as ei:
        wall.admit(
            route="learning.read",
            token="tok-teacher",
            payload={"subject_uuid": "u1"},
            attributes={"institution_uuid": "inst-OTHER"},
        )
    assert ei.value.reason is DenyReason.ABAC_DENIED


# --- consent gate ----------------------------------------------------------- #


def test_consent_required_for_cross_context_read():
    wall, audit = make_wall()
    # teacher lacks intelligence-views.read consent scope.
    with pytest.raises(WallDenied) as ei:
        wall.admit(
            route="intelligence-views.read",
            token="tok-teacher",
            payload={"subject_uuid": "u1"},
            attributes={"institution_uuid": "inst-1"},
            cross_context=True,
        )
    assert ei.value.reason is DenyReason.CONSENT_REQUIRED


def test_consent_satisfied_admits_cross_context_read():
    wall, audit = make_wall()
    result = wall.admit(
        route="learning.read",
        token="tok-teacher",
        payload={"subject_uuid": "u1"},
        attributes={"institution_uuid": "inst-1"},
        cross_context=True,
    )
    assert result.allowed is True


# --- permission ladder ------------------------------------------------------ #


def test_consequential_export_requires_human_approval():
    wall, audit = make_wall()
    with pytest.raises(WallDenied) as ei:
        wall.admit(
            route="feature-store.export",
            token="tok-admin",
            payload={"subject_uuid": "u1"},
            attributes={"institution_uuid": "inst-1"},
        )
    assert ei.value.reason is DenyReason.APPROVAL_REQUIRED


def test_consequential_export_with_approval_admits():
    wall, audit = make_wall()
    result = wall.admit(
        route="feature-store.export",
        token="tok-admin",
        payload={"subject_uuid": "u1"},
        attributes={"institution_uuid": "inst-1"},
        approval_token="approved-by-human-123",
    )
    assert result.allowed is True


# --- child safety ----------------------------------------------------------- #


def test_child_safety_blocks_unsafe_free_text():
    wall, audit = make_wall(child_safety=BlockWordChildSafety())
    with pytest.raises(WallDenied) as ei:
        wall.admit(
            route="communication.write",
            token="tok-teacher",
            payload={"subject_uuid": "u1", "note": "this is blocked content"},
            attributes={"institution_uuid": "inst-1"},
        )
    assert ei.value.reason is DenyReason.CHILD_SAFETY_BLOCKED


def test_child_safety_allows_safe_free_text():
    wall, audit = make_wall(child_safety=BlockWordChildSafety())
    result = wall.admit(
        route="communication.write",
        token="tok-teacher",
        payload={"subject_uuid": "u1", "note": "great progress this week"},
        attributes={"institution_uuid": "inst-1"},
    )
    assert result.allowed is True


# --- rate limit through the wall ------------------------------------------- #


def test_wall_enforces_rate_limit_and_audits():
    registry = build_default_registry()
    limiter = RateLimiter(
        default_rule=RateLimitRule(limit=1000, window_seconds=60),
        route_rules={"learning.read": RateLimitRule(limit=1, window_seconds=60)},
        clock=FakeClock(),
    )
    teacher = Principal(
        canonical_uuid="uuid-teacher", roles=("teacher",), institution_uuid="inst-1"
    )
    audit = InMemoryAuditSink()
    wall = Wall(
        registry=registry,
        limiter=limiter,
        verifier=FakeVerifier({"t": teacher}),
        consent=FakeConsent(),
        child_safety=AllowAllChildSafety(),
        audit=audit,
        clock=FakeClock(),
    )
    payload = {"subject_uuid": "u1"}
    attrs = {"institution_uuid": "inst-1"}
    assert wall.admit(route="learning.read", token="t", payload=payload, attributes=attrs).allowed
    with pytest.raises(WallDenied) as ei:
        wall.admit(route="learning.read", token="t", payload=payload, attributes=attrs)
    assert ei.value.reason is DenyReason.RATE_LIMITED
    assert audit.events[-1].reason == "rate_limited"


# --- safe defaults degrade closed ------------------------------------------ #


def test_default_verifier_denies_all_tokens():
    # No verifier injected -> every token invalid (fails closed).
    registry = build_default_registry()
    limiter = RateLimiter(default_rule=RateLimitRule(limit=100, window_seconds=60), clock=FakeClock())
    wall = Wall(registry=registry, limiter=limiter, clock=FakeClock())
    with pytest.raises(WallDenied) as ei:
        wall.admit(route="learning.read", token="anything", payload={"subject_uuid": "u1"})
    assert ei.value.reason is DenyReason.INVALID_TOKEN


def test_audit_is_append_only():
    wall, audit = make_wall()
    before = len(audit.events)
    with pytest.raises(WallDenied):
        wall.admit(route="learning.read", token=None)
    # earlier events are never removed; the sink only grows.
    assert len(audit.events) == before + 1
    # records carry only the opaque uuid, no PII fields exist on the event.
    ev = audit.events[-1]
    assert set(vars(ev).keys()) == {"ts", "actor_uuid", "route", "allowed", "reason"}
