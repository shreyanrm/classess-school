"""Routable capability registry -- the wall's route map.

"Every call passes the wall." This module declares every FEATURE / capability
module as a routable capability behind the full enforcement chain:

    rate-limit  ->  schema-validate  ->  authn (token)  ->  RBAC  ->  ABAC
                ->  consent gate      ->  child-safety (free text)  ->  audit

The capability module HTTP handlers are intentionally thin -- the point is that
the WALL enforces access, not the module. A module that is not declared here is
simply not routable: an unknown route fails closed.

Capability modules covered this wave:
    institution, scheduling, coursework, learning, content, learner-record,
    communication, intelligence-views, attendance, planning, classroom,
    teacher-growth, integration, feature-store.

This module is import-safe and has no network/DB dependency. Authentication,
policy and consent/audit are injected as callables so the gateway can supply its
real implementations while tests supply fakes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ratelimit import Algorithm, RateLimiter, RateLimitRule
from .validation import FieldSpec, FieldType, RequestSchema, SchemaRegistry


# --------------------------------------------------------------------------- #
# Capability declaration
# --------------------------------------------------------------------------- #


class Action(str, Enum):
    READ = "read"
    WRITE = "write"
    # Consequential actions need human approval and never auto-fire
    # (permission ladder).
    APPROVE = "approve"
    EXPORT = "export"
    # The proactive-loop / permission-ladder rungs (spine A5 workflow runtime):
    #   recommend -> approve -> execute. RECOMMEND surfaces a suggestion (the
    #   lowest, non-consequential rung). APPROVE records the human decision (the
    #   gate itself — it does not require a prior approval token). EXECUTE is the
    #   execute-with-permission rung for a consequential action: it is marked
    #   consequential so the WALL forces an X-Approval-Token (it can never
    #   auto-fire). The consequential write verbs (grade/send/publish/delete/
    #   charge) route onto EXECUTE so the wall gates them on the ladder.
    RECOMMEND = "recommend"
    EXECUTE = "execute"


@dataclass(frozen=True)
class Capability:
    """One routable capability behind the wall."""

    module: str
    action: Action
    # RBAC: roles permitted to even attempt this capability.
    roles: Tuple[str, ...]
    # ABAC: attribute predicate over the request context. Returns True if the
    # attribute constraints are satisfied (e.g. same institution, owns record).
    abac: Optional[Callable[["RequestContext"], bool]] = None
    # Consent: when set, a cross-context read requires a granted consent scope.
    consent_scope: Optional[str] = None
    # Whether this capability mutates behavioural / consequential state and so
    # sits on the human-approval rung of the permission ladder.
    consequential: bool = False
    # Per-route request schema (validated at the wall).
    schema: RequestSchema = field(default_factory=lambda: RequestSchema())
    # Per-route rate limit. None -> use the limiter default.
    rate_limit: Optional[RateLimitRule] = None

    @property
    def route(self) -> str:
        return f"{self.module}.{self.action.value}"


# --------------------------------------------------------------------------- #
# Request context (carries NO PII -- only opaque canonical_uuid + attributes)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Principal:
    # Opaque canonical identifier; never PII.
    canonical_uuid: str
    roles: Tuple[str, ...]
    institution_uuid: Optional[str] = None
    # consent scopes the principal currently holds (granted, unexpired)
    consent_scopes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class RequestContext:
    principal: Principal
    route: str
    payload: Dict[str, Any] = field(default_factory=dict)
    # attributes resolved by the gateway for ABAC, e.g. target institution.
    attributes: Dict[str, Any] = field(default_factory=dict)
    # whether this read crosses a context boundary (triggers consent gate).
    cross_context: bool = False
    # human approval token for consequential actions (permission ladder).
    approval_token: Optional[str] = None


# --------------------------------------------------------------------------- #
# Enforcement outcomes
# --------------------------------------------------------------------------- #


class DenyReason(str, Enum):
    UNKNOWN_ROUTE = "unknown_route"
    NO_TOKEN = "no_token"
    INVALID_TOKEN = "invalid_token"
    RATE_LIMITED = "rate_limited"
    SCHEMA_INVALID = "schema_invalid"
    RBAC_DENIED = "rbac_denied"
    ABAC_DENIED = "abac_denied"
    CONSENT_REQUIRED = "consent_required"
    APPROVAL_REQUIRED = "approval_required"
    CHILD_SAFETY_BLOCKED = "child_safety_blocked"


class WallDenied(Exception):
    def __init__(self, reason: DenyReason, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #


class CapabilityRegistry:
    def __init__(self) -> None:
        self._caps: Dict[str, Capability] = {}
        self.schemas = SchemaRegistry()

    def register(self, cap: Capability) -> None:
        if cap.route in self._caps:
            raise ValueError(f"capability already registered: {cap.route}")
        self._caps[cap.route] = cap
        self.schemas.register(cap.route, cap.schema)

    def get(self, route: str) -> Optional[Capability]:
        return self._caps.get(route)

    def has(self, route: str) -> bool:
        return route in self._caps

    def routes(self) -> List[str]:
        return sorted(self._caps.keys())

    def modules(self) -> List[str]:
        return sorted({c.module for c in self._caps.values()})

    def apply_rate_limits(self, limiter: RateLimiter) -> None:
        """Seed each capability's declared rate-limit into the limiter.

        Declared limits are defaults: a rule already configured on the limiter
        (from config or the caller) is left intact (``overwrite=False``).
        """
        for cap in self._caps.values():
            if cap.rate_limit is not None:
                limiter.register_route(cap.route, cap.rate_limit, overwrite=False)


# --------------------------------------------------------------------------- #
# Default capability map for the feature modules
# --------------------------------------------------------------------------- #

# Shared schemas -------------------------------------------------------------

_READ_SCHEMA = RequestSchema(
    fields={
        # Opaque subject id; the only identifier behavioural data may carry.
        "subject_uuid": FieldSpec(FieldType.STRING, required=True, min_length=1),
        "view": FieldSpec(FieldType.STRING, required=False, max_length=64),
    },
    strict=True,
)

# A write surface with a free-text note -> child-safety screened by the wall.
_WRITE_NOTE_SCHEMA = RequestSchema(
    fields={
        "subject_uuid": FieldSpec(FieldType.STRING, required=True, min_length=1),
        "note": FieldSpec(
            FieldType.STRING, required=False, max_length=4000, free_text=True
        ),
    },
    strict=True,
)

# The proactive-loop envelope the wall governs (recommend / approve / execute).
# It carries opaque refs only: the recommendation under decision, the human's
# decision (approve/adjust/decline), and the consequence flag the surface marks.
# The full domain payload (evidence, signals) is the MODULE's concern and travels
# to the engine handler; the wall validates only this admission envelope. A
# free-text adjustment note is child-safety screened by the wall.
_LOOP_SCHEMA = RequestSchema(
    fields={
        "subject_uuid": FieldSpec(FieldType.STRING, required=False, min_length=1),
        "recommendation_id": FieldSpec(FieldType.STRING, required=False, min_length=1),
        "decision": FieldSpec(
            FieldType.STRING, required=False,
            choices=("approve", "adjust", "decline"),
        ),
        "decided_by": FieldSpec(FieldType.STRING, required=False, min_length=1),
        "consequential": FieldSpec(FieldType.BOOLEAN, required=False),
        "adjustment": FieldSpec(
            FieldType.STRING, required=False, max_length=2000, free_text=True
        ),
    },
    strict=True,
)

# Standard role bundles ------------------------------------------------------
_STAFF = ("admin", "teacher", "coordinator")
_ADMIN = ("admin",)
_TEACHER = ("admin", "teacher")
_ALL = ("admin", "teacher", "coordinator", "learner", "guardian", "service")


def _same_institution(ctx: RequestContext) -> bool:
    """ABAC: principal may only act within their own institution."""
    target = ctx.attributes.get("institution_uuid")
    if target is None:
        return True  # no institution scoping on this request
    return ctx.principal.institution_uuid == target


# Default limits (config-driven in production via RateLimiter.from_config).
_READ_LIMIT = RateLimitRule(limit=120, window_seconds=60, algorithm=Algorithm.TOKEN_BUCKET)
_WRITE_LIMIT = RateLimitRule(limit=30, window_seconds=60, algorithm=Algorithm.TOKEN_BUCKET)
_EXPORT_LIMIT = RateLimitRule(limit=5, window_seconds=60, algorithm=Algorithm.FIXED_WINDOW)


# (module, has_write, has_export, consent_scope_for_cross_context)
_MODULE_PLAN: Tuple[Tuple[str, bool, bool, Optional[str]], ...] = (
    ("institution", True, True, None),
    ("scheduling", True, False, None),
    ("coursework", True, False, "coursework.read"),
    ("learning", True, False, "learning.read"),
    ("content", True, False, None),
    ("learner-record", False, True, "learner-record.read"),
    ("communication", True, False, "communication.read"),
    ("intelligence-views", False, True, "intelligence-views.read"),
    ("attendance", True, False, "attendance.read"),
    ("planning", True, False, None),
    ("classroom", True, False, None),
    ("teacher-growth", True, False, "teacher-growth.read"),
    ("integration", True, False, None),
    ("feature-store", False, True, "feature-store.read"),
    # The GOVERNANCE control plane (GAP#3/#5/#7): the audit-trail READ + the
    # consequential control writes (AI-control toggle / break-glass / policy
    # version / emergency disable). The writes ride the EXECUTE rung (registered
    # below) so the wall forces an approval token; READ is the audit-trail query.
    ("governance", False, False, None),
)


def build_default_registry() -> CapabilityRegistry:
    """Register all feature modules as routable capabilities behind the wall."""
    reg = CapabilityRegistry()
    for module, has_write, has_export, consent_scope in _MODULE_PLAN:
        # READ -- gated by RBAC + ABAC (+ consent on cross-context reads).
        reg.register(
            Capability(
                module=module,
                action=Action.READ,
                roles=_ALL,
                abac=_same_institution,
                consent_scope=consent_scope,
                consequential=False,
                schema=_READ_SCHEMA,
                rate_limit=_READ_LIMIT,
            )
        )
        if has_write:
            reg.register(
                Capability(
                    module=module,
                    action=Action.WRITE,
                    roles=_STAFF,
                    abac=_same_institution,
                    consent_scope=None,
                    consequential=False,
                    schema=_WRITE_NOTE_SCHEMA,
                    rate_limit=_WRITE_LIMIT,
                )
            )
        if has_export:
            # Exports are consequential -> need human approval, never auto-fire.
            reg.register(
                Capability(
                    module=module,
                    action=Action.EXPORT,
                    roles=_ADMIN,
                    abac=_same_institution,
                    consent_scope=consent_scope,
                    consequential=True,
                    schema=_READ_SCHEMA,
                    rate_limit=_EXPORT_LIMIT,
                )
            )

        # --- The proactive-loop rungs: recommend -> approve -> execute ------ #
        # Every module's proactive behaviour rides the spine A5 workflow loop.
        # RECOMMEND surfaces a suggestion (lowest, non-consequential rung).
        reg.register(
            Capability(
                module=module,
                action=Action.RECOMMEND,
                roles=_ALL,
                abac=_same_institution,
                consent_scope=consent_scope,
                consequential=False,
                schema=_LOOP_SCHEMA,
                rate_limit=_READ_LIMIT,
            )
        )
        # APPROVE records the human decision — the gate itself, so it does NOT
        # require a prior approval token (that would be circular). Staff-gated.
        reg.register(
            Capability(
                module=module,
                action=Action.APPROVE,
                roles=_STAFF,
                abac=_same_institution,
                consent_scope=None,
                consequential=False,
                schema=_LOOP_SCHEMA,
                rate_limit=_WRITE_LIMIT,
            )
        )
        # EXECUTE is the execute-with-permission rung for a consequential action.
        # It is CONSEQUENTIAL: the wall forces an X-Approval-Token (step 8) and it
        # can never auto-fire. The consequential write verbs (grade/send/publish/
        # delete/charge) route onto this action in the deployable door.
        reg.register(
            Capability(
                module=module,
                action=Action.EXECUTE,
                roles=_STAFF,
                abac=_same_institution,
                consent_scope=None,
                consequential=True,
                schema=_LOOP_SCHEMA,
                rate_limit=_WRITE_LIMIT,
            )
        )
    return reg
