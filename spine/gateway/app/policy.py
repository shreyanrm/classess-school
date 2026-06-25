"""The policy engine — RBAC + ABAC, evaluated at the wall (INVARIANT 3).

DENY BY DEFAULT. A request is allowed only when an explicit rule matches the
caller's resolved memberships (RBAC) and the request attributes satisfy any
ABAC constraints. Every decision carries human-readable reasons for the audit
record and for explainability.

The rule table here is the Ring 0 baseline for the two reachable capabilities
(identity, event-store). It is deliberately small, explicit, and additive:
later capabilities register their rules without touching the engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from .models import PolicyDecision, VerifiedIdentity

# A capability.operation pair -> the roles allowed to invoke it (RBAC), plus an
# optional ABAC predicate over (identity, resource_scope, purpose).
AbacPredicate = Callable[[VerifiedIdentity, str | None, str | None], tuple[bool, str]]


@dataclass(frozen=True)
class Rule:
    capability: str
    operation: str
    allowed_roles: frozenset[str]
    purposes: frozenset[str] | None = None  # None => any; else purpose must be in the set
    abac: AbacPredicate | None = None
    description: str = ""


def _scope_contains(identity: VerifiedIdentity, resource_scope: str | None, _purpose: str | None) -> tuple[bool, str]:
    """ABAC: the caller may only act within a scope covered by a membership.

    Resource scope is a serialized attribute string (e.g. an institution id or a
    JSON object). A membership whose scope is a superset (by simple containment
    of attributes) satisfies the constraint. Admins are scoped too — there is no
    global bypass at this layer.
    """
    if resource_scope is None:
        return True, "no resource scope asserted"
    req = _parse_scope(resource_scope)
    for m in identity.memberships:
        have = _parse_scope(m.scope)
        if _covers(have, req):
            return True, f"membership scope covers resource scope ({m.role})"
    return False, "no membership scope covers the requested resource scope"


def _parse_scope(scope: str) -> dict:
    try:
        val = json.loads(scope)
        return val if isinstance(val, dict) else {"_": val}
    except (json.JSONDecodeError, TypeError):
        return {"_": scope}


def _covers(have: dict, req: dict) -> bool:
    """have covers req when every attribute in req is present and equal in have.
    An empty have ({}) covers nothing specific (deny-by-default)."""
    if not req:
        return True
    return all(k in have and have[k] == v for k, v in req.items())


# ---------------------------------------------------------------------------
# The Ring 0 baseline rule table. Additive — capabilities append their rules.
# ---------------------------------------------------------------------------
_ALL_ROLES = frozenset({"admin", "teacher", "student", "parent"})
_STAFF = frozenset({"admin", "teacher"})


@dataclass
class PolicyEngine:
    rules: dict[tuple[str, str], Rule] = field(default_factory=dict)

    @classmethod
    def baseline(cls) -> "PolicyEngine":
        engine = cls()
        baseline_rules = [
            # Identity: introspection and own-membership resolution.
            Rule("identity", "resolveMemberships", _ALL_ROLES,
                 description="Resolve own memberships."),
            Rule("identity", "consentCheck", _ALL_ROLES,
                 description="Check a consent + purpose (INVARIANT 6)."),
            Rule("identity", "consentGrant", _ALL_ROLES,
                 description="Capture a consent grant."),
            # Privileged provisioning of canonical users — staff only.
            Rule("identity", "issueCanonicalUser", frozenset({"admin"}),
                 description="Privileged: issue a canonical user."),
            # Event store: emit requires staff or student (the slice producers);
            # reads are purpose-gated and scope-checked.
            Rule("event-store", "emitEvent", _ALL_ROLES,
                 description="Append an attributed event."),
            Rule("event-store", "readEvents", _STAFF | frozenset({"student", "parent"}),
                 abac=_scope_contains,
                 description="Governed, consent-scoped read (INVARIANT 6) within scope."),
            Rule("event-store", "readEvent", _STAFF | frozenset({"student", "parent"}),
                 abac=_scope_contains,
                 description="Governed single-event read within scope."),
            # Generate-and-verify generators (B3/d6) — STAFF only, deny by
            # default otherwise. PREPARE rung: each PREPARES a draft behind the
            # confidence gate (publishing/assigning is the separate consequential
            # human act). Scope-checked so a teacher acts only within a covered
            # institution. Generation is not a cross-context read, so no purpose.
            Rule("content", "generate-worksheet", _STAFF, abac=_scope_contains,
                 description="Prepare a verified worksheet (draft; not assigned)."),
            Rule("content", "generate-and-verify-content", _STAFF, abac=_scope_contains,
                 description="Prepare verified content incl. lesson visuals (draft)."),
            Rule("planning", "generate-course-outline", _STAFF, abac=_scope_contains,
                 description="Prepare a verified course outline (draft; not published)."),
            Rule("planning", "generate-lesson-plan", _STAFF, abac=_scope_contains,
                 description="Prepare a lesson plan (draft; not published)."),
            Rule("planning", "generate-session-plan", _STAFF, abac=_scope_contains,
                 description="Prepare a session plan (draft; not published)."),
            # PERSONALIZATION — the consent + age-tier-gated implicit-profiling
            # capability powering §1 onboarding. INFER re-derives the learner's
            # PROVISIONAL profile from light behavioural signals and emits a
            # consent-stamped profile.updated event; it reads behavioural signals
            # across a context boundary, so a purpose assertion is required
            # (INVARIANT 6) and the depth is bounded inside the module by the
            # consent + age tier (DPDP). Any role may drive onboarding profiling
            # for itself (a learner, or staff/guardian setting up an account);
            # deny-by-default otherwise. HINTS turns the profile into learner-safe
            # surface hints (also purpose-asserted, consent-scoped).
            Rule("personalization", "infer", _ALL_ROLES, abac=_scope_contains,
                 purposes=frozenset({"account", "personalization"}),
                 description="Re-derive the provisional profile + emit profile.updated (consent + age-tier gated)."),
            Rule("personalization", "hints", _ALL_ROLES, abac=_scope_contains,
                 purposes=frozenset({"account", "personalization"}),
                 description="Project the gated profile into learner-safe surface hints."),
        ]
        for r in baseline_rules:
            engine.register(r)
        return engine

    def register(self, rule: Rule) -> None:
        self.rules[(rule.capability, rule.operation)] = rule

    def evaluate(
        self,
        *,
        identity: VerifiedIdentity,
        capability: str,
        operation: str,
        resource_scope: str | None,
        purpose: str | None,
    ) -> PolicyDecision:
        reasons: list[str] = []
        rule = self.rules.get((capability, operation))
        if rule is None:
            # DENY BY DEFAULT: no explicit rule => no access.
            return PolicyDecision(
                decision="deny",
                reasons=[f"deny by default: no policy rule for {capability}.{operation}"],
            )

        roles = {m.role for m in identity.memberships if m.app == identity.app}
        if not roles:
            return PolicyDecision(decision="deny", reasons=["no active membership in app"])

        granting = roles & rule.allowed_roles
        if not granting:
            return PolicyDecision(
                decision="deny",
                reasons=[f"role(s) {sorted(roles)} not permitted for {capability}.{operation}"],
            )
        reasons.append(f"RBAC: role(s) {sorted(granting)} permit {capability}.{operation}")

        if rule.purposes is not None:
            if purpose is None or purpose not in rule.purposes:
                return PolicyDecision(
                    decision="deny",
                    reasons=reasons + [f"purpose '{purpose}' not in allowed {sorted(rule.purposes)}"],
                )
            reasons.append(f"purpose '{purpose}' permitted")

        if rule.abac is not None:
            ok, why = rule.abac(identity, resource_scope, purpose)
            reasons.append(f"ABAC: {why}")
            if not ok:
                return PolicyDecision(decision="deny", reasons=reasons)

        return PolicyDecision(decision="allow", reasons=reasons)
